import os
import json
import csv
import io
import smtplib
import ssl
import logging
import re
import socket
import random
from datetime import datetime, timezone, timedelta
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, EndpointConnectionError, ReadTimeoutError, ConnectTimeoutError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ---------- Global timeouts ----------
DEFAULT_CONNECT_TIMEOUT = int(os.getenv("CONNECT_TIMEOUT_SECONDS", "5"))
DEFAULT_READ_TIMEOUT    = int(os.getenv("READ_TIMEOUT_SECONDS", "20"))
SMTP_SOCKET_TIMEOUT     = float(os.getenv("SMTP_SOCKET_TIMEOUT", "8"))
socket.setdefaulttimeout(SMTP_SOCKET_TIMEOUT)

# -------------------- Env helpers --------------------
def getenv_bool(key: str, default: bool = True) -> bool:
    v = os.getenv(key)
    if v is None:
        return default
    return v.strip().lower() in ("1","true","yes","y")

def getenv_list(key: str):
    v = os.getenv(key, "")
    if not v.strip():
        return []
    return [x.strip() for x in v.split(",") if x.strip()]

def getenv_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except Exception:
        return default

# -------------------- Filters --------------------
def make_time_filter(days_back: int):
    # SecurityHub supports DateRange for UpdatedAt
    return {"UpdatedAt": [{"DateRange": {"Value": days_back, "Unit": "DAYS"}}]}

def make_optional_filters(rule_title_prefix, rule_prefix, compliance_statuses, workflow_statuses):
    """
    If RULE_TITLE_PREFIX is set, filter Title by PREFIX (e.g., BMOASR-ConfigRule-HCOPS-).
    Else if RULE_PREFIX is set, filter GeneratorId by CONTAINS.
    Also allows filtering by ComplianceStatus, WorkflowStatus, and RecordState (default ACTIVE).
    """
    f = {}
    if rule_title_prefix:
        f["Title"] = [{"Value": rule_title_prefix, "Comparison": "PREFIX"}]
    elif rule_prefix:
        f["GeneratorId"] = [{"Value": rule_prefix, "Comparison": "CONTAINS"}]

    if compliance_statuses:
        f["ComplianceStatus"] = [{"Value": s, "Comparison": "EQUALS"} for s in compliance_statuses]
    if workflow_statuses:
        f["WorkflowStatus"] = [{"Value": s, "Comparison": "EQUALS"} for s in workflow_statuses]

    # Default to ACTIVE to avoid archived records unless explicitly overridden
    record_state = os.getenv("RECORD_STATE", "ACTIVE").strip().upper()
    if record_state:
        f["RecordState"] = [{"Value": record_state, "Comparison": "EQUALS"}]
    return f

def merge_filters(base_filters, extra_filters):
    if not extra_filters:  return base_filters or {}
    if not base_filters:   return extra_filters
    merged = dict(base_filters)
    for k, v in extra_filters.items():
        if k in merged and isinstance(merged[k], list) and isinstance(v, list):
            merged[k] = merged[k] + v
        else:
            merged[k] = v
    return merged

# -------------------- Finding helpers --------------------
def parse_dt(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None

def derive_rule_name(f: dict) -> str:
    """
    Prefer Title as the 'full rule name'.
    If Title not present, fall back to UserDefined/ProductFields, then GeneratorId parsing.
    """
    title = f.get("Title")
    if title:
        return str(title)

    udf = f.get("UserDefinedFields") or {}
    if isinstance(udf, dict):
        rn = udf.get("RuleName")
        if rn: return str(rn)

    pf = f.get("ProductFields") or {}
    if isinstance(pf, dict):
        rn = pf.get("RuleName") or pf.get("ruleName")
        if rn: return str(rn)

    gen = f.get("GeneratorId", "") or ""
    if "/config-rule/" in gen:
        return gen.split("/config-rule/")[-1]
    if "/" in gen:
        return gen.rsplit("/", 1)[-1]
    return gen or "unknown"

def dedupe_latest(findings, key_mode: str = "GENERATOR_ID"):
    """
    key_mode:
      - GENERATOR_ID: one latest row per GeneratorId
      - ACCOUNT_RULE: one latest row per (AwsAccountId, RuleName)
    """
    latest = {}
    for f in findings:
        generator_id = f.get("GeneratorId", "unknown")
        rule_name = derive_rule_name(f)
        acct = f.get("AwsAccountId", "unknown")
        key = (acct, rule_name) if key_mode == "ACCOUNT_RULE" else generator_id

        cur_dt = parse_dt(f.get("UpdatedAt", "")) or datetime.min.replace(tzinfo=timezone.utc)
        prev = latest.get(key)
        if not prev or cur_dt > (parse_dt(prev.get("UpdatedAt", "")) or datetime.min.replace(tzinfo=timezone.utc)):
            latest[key] = f
    return list(latest.values())

# -------------------- Security Hub query (concurrent & capped) --------------------
def _collect_region_findings(region: str, filters, page_size: int, max_pages: int, max_findings: int):
    out = []
    sh = boto3.client(
        "securityhub",
        region_name=region,
        config=Config(
            retries={"max_attempts": 10, "mode": "standard"},
            connect_timeout=DEFAULT_CONNECT_TIMEOUT,
            read_timeout=DEFAULT_READ_TIMEOUT,
        ),
    )
    try:
        paginator = sh.get_paginator("get_findings")
        page_count = 0
        for page in paginator.paginate(Filters=filters, PaginationConfig={"PageSize": page_size}):
            page_count += 1
            for f in page.get("Findings", []):
                f["_Region"] = region  # for internal debugging only; NOT exported
                out.append(f)
                if max_findings and len(out) >= max_findings:
                    return out
            if max_pages and page_count >= max_pages:
                break
    except (ClientError, EndpointConnectionError, ReadTimeoutError, ConnectTimeoutError) as e:
        logger.error("Region %s query error: %s", region, e, exc_info=True)
    return out

def collect_findings(regions, filters):
    page_size    = getenv_int("PAGE_SIZE", 100)
    max_pages    = getenv_int("MAX_PAGES", 0)        # 0 = no cap
    max_findings = getenv_int("MAX_FINDINGS", 0)     # 0 = no cap
    max_workers  = getenv_int("MAX_REGION_WORKERS", min(4, len(regions) or 1))

    allf = []
    with ThreadPoolExecutor(max_workers=max_workers) as exe:
        futs = {exe.submit(_collect_region_findings, r, filters, page_size, max_pages, max_findings): r for r in regions}
        for fut in as_completed(futs):
            r = futs[fut]
            try:
                allf.extend(fut.result())
            except Exception as e:
                logger.error("Region %s worker failed: %s", r, e, exc_info=True)
    logger.info("Collected findings total: %d", len(allf))
    return allf

# -------------------- CSV helpers for Resources & Tags --------------------
def json_safe(x):
    try:
        return json.dumps(x, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return str(x)

def _tags_to_dict(tags_field):
    out = {}
    if isinstance(tags_field, list):
        for t in tags_field:
            if not isinstance(t, dict):
                continue
            k = (t.get("Key") or "").strip()
            v = t.get("Value")
            if k:
                out[k.lower()] = v
    elif isinstance(tags_field, dict):
        for k, v in tags_field.items():
            if isinstance(k, str):
                out[k.lower()] = v
    return out

def _extract_any_tags_from_resource(res: dict):
    """
    Returns tags map (lowercased keys) from:
    - res['Tags'] if present (list[{Key,Value}] or dict)
    - or the first Details.* that contains 'Tags'
    """
    t = res.get("Tags")
    tags = _tags_to_dict(t)
    if tags:
        return tags

    details = res.get("Details")
    if isinstance(details, dict):
        for _, v in details.items():
            if isinstance(v, dict) and "Tags" in v:
                tags = _tags_to_dict(v.get("Tags"))
                if tags:
                    return tags
    return {}

def _primary_resource(finding: dict) -> tuple[dict, int]:
    """Return (resource_dict, index) choosing the first with Tags; else the first resource; else ({}, -1)."""
    resources = finding.get("Resources") or []
    if not isinstance(resources, list):
        return {}, -1
    for idx, r in enumerate(resources):
        if isinstance(r, dict) and _extract_any_tags_from_resource(r):
            return r, idx
    return (resources[0], 0) if resources else ({}, -1)

def _get(d: dict, dotted: str, default=""):
    cur = d
    for p in dotted.split("."):
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return default
    return cur

# --- NEW: normalize tag keys (case- and punctuation-insensitive) ---
def _norm_tag_key(s: str) -> str:
    # Lowercase and remove non [a-z0-9]; turns "Support-Team" / "support team" / "support_team" -> "supportteam"
    return re.sub(r"[^a-z0-9]+", "", str(s or "").lower())

# ---------- AccountId display: force full digits in Excel/Sheets ----------
def _excel_safe_account(x) -> str:
    """
    Return an Account ID formatted to avoid scientific notation in Excel/Sheets.
    - If numeric-looking: returns => ="123456789012" (displays full number)
    - Else: returns as-is string
    """
    s = str(x or "").strip()
    if not s:
        return ""
    if s.isdigit():
        return f'="{s}"'
    return s

def _account_id_from_resource(res: dict, finding: dict) -> str:
    """
    Prefer resource.AccountId; else parse from ARN in Resource.Id; else finding.AwsAccountId.
    """
    if isinstance(res, dict):
        acc = res.get("AccountId") or res.get("accountId")
        if acc:
            return str(acc)
        rid = res.get("Id") or res.get("id") or ""
        if isinstance(rid, str) and rid.startswith("arn:"):
            parts = rid.split(":")
            if len(parts) >= 6 and parts[4]:
                return parts[4]
    return str(finding.get("AwsAccountId", ""))

# -------------------- Summary (Workflow × Compliance) --------------------
def build_workflow_compliance_summary(findings):
    """
    Returns:
      counts: dict[(workflow, compliance)] -> int (unique resources)
      workflows: sorted list of workflow statuses present
      compliances: sorted list of compliance statuses present
    Uniqueness key: (accountId, resourceId).
    """
    combo_to_set = {}
    workflows = set()
    compliances = set()

    for f in findings:
        wf = (f.get("Workflow", {}) or {}).get("Status", "") or ""
        cp = (f.get("Compliance", {}) or {}).get("Status", "") or ""
        workflows.add(wf)
        compliances.add(cp)

        res, _ = _primary_resource(f)
        rid = res.get("Id") or res.get("id") or "" if isinstance(res, dict) else ""
        acct = _account_id_from_resource(res, f)
        keyres = (acct, rid)

        combo = (wf, cp)
        s = combo_to_set.setdefault(combo, set())
        if keyres != ("", ""):
            s.add(keyres)

    # Friendly ordering, but keep unknowns too
    wf_order = ["NEW", "NOTIFIED", "RESOLVED", "SUPPRESSED", ""]
    cp_order = ["FAILED", "WARNING", "PASSED", "NOT_AVAILABLE", ""]
    wf_sorted = sorted(workflows, key=lambda x: (wf_order.index(x) if x in wf_order else len(wf_order), x))
    cp_sorted = sorted(compliances, key=lambda x: (cp_order.index(x) if x in cp_order else len(cp_order), x))

    counts = {k: len(v) for k, v in combo_to_set.items()}
    return counts, wf_sorted, cp_sorted

def summary_to_html(counts, workflows, compliances) -> str:
    """Sleek HTML grid for email body."""
    th = 'style="padding:6px 10px;border-bottom:1px solid #e5e7eb;text-align:center;font-weight:600;white-space:nowrap"'
    td = 'style="padding:6px 10px;border-bottom:1px solid #f1f5f9;text-align:center"'
    hd = 'style="padding:6px 10px;background:#f8fafc;border-bottom:1px solid #e5e7eb;text-align:center;font-weight:700"'
    wrap = 'style="border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;font-family:system-ui, -apple-system, Segoe UI, Roboto, Arial; font-size:13px; color:#0f172a"'

    # Pre-calc totals
    col_totals = {c: 0 for c in compliances}
    row_totals = {w: 0 for w in workflows}
    grand_total = 0
    for w in workflows:
        for c in compliences := compliances:  # Python 3.8+/walrus ok; replace if needed
            v = counts.get((w, c), 0)
            row_totals[w] += v
            col_totals[c] += v
            grand_total += v

    html = []
    html.append(f'<div {wrap}>')
    html.append('<table style="border-collapse:collapse;width:100%">')
    # Header row
    html.append('<tr>')
    html.append(f'<th {hd} style="text-align:left;padding:8px 10px;border-bottom:1px solid #e5e7eb">Workflow \\ Compliance</th>')
    for c in compliances:
        html.append(f'<th {th}>{c or "&nbsp;"}</th>')
    html.append(f'<th {th}>TOTAL</th>')
    html.append('</tr>')

    # Data rows
    for w in workflows:
        html.append('<tr>')
        html.append(f'<td style="padding:6px 10px;border-bottom:1px solid #f1f5f9;text-align:left;font-weight:600">{w or "&nbsp;"}</td>')
        for c in compliances:
            v = counts.get((w, c), 0)
            html.append(f'<td {td}>{v}</td>')
        html.append(f'<td {td}><b>{row_totals[w]}</b></td>')
        html.append('</tr>')

    # Footer totals
    html.append('<tr>')
    html.append(f'<td style="padding:6px 10px;background:#f8fafc;border-top:1px solid #e5e7eb;text-align:left;font-weight:700">TOTAL</td>')
    for c in compliances:
        html.append(f'<td style="padding:6px 10px;background:#f8fafc;border-top:1px solid #e5e7eb;text-align:center;font-weight:700">{col_totals[c]}</td>')
    html.append(f'<td style="padding:6px 10px;background:#f8fafc;border-top:1px solid #e5e7eb;text-align:center;font-weight:800">{grand_total}</td>')
    html.append('</tr>')

    html.append('</table></div>')
    return "".join(html)

def summary_explanations_html(counts, workflows, compliances) -> str:
    """
    Short bullets like: NEW × PASSED — 5 unique resources.
    Only prints combos with count > 0.
    """
    if not counts:
        return ""

    wf_hint = {
        "NEW": "newly created or reopened",
        "NOTIFIED": "owners have been notified",
        "RESOLVED": "workflow closed",
        "SUPPRESSED": "intentionally suppressed",
        "": "unspecified workflow"
    }
    cp_hint = {
        "FAILED": "currently non-compliant",
        "WARNING": "at-risk or warning",
        "PASSED": "currently compliant",
        "NOT_AVAILABLE": "no compliance status",
        "": "unspecified compliance"
    }

    items = []
    for w in workflows:
        for c in compliances:
            n = counts.get((w, c), 0)
            if n > 0:
                wh = wf_hint.get(w, "workflow")
                ch = cp_hint.get(c, "compliance")
                items.append(f'<li><b>{w or "UNSPECIFIED"}</b> × <b>{c or "UNSPECIFIED"}</b> — {n} unique resources '
                             f'({wh}; {ch}).</li>')

    if not items:
        return ""

    return '<ul style="margin:10px 0 0 18px; padding:0; color:#334155; font-size:13px">' + "".join(items) + "</ul>"

# -------------------- CSV (same order; AccountIds forced to full digits) --------------------
def to_csv_bytes(findings):
    # Fixed set of tag columns you requested (headers preserved exactly)
    tag_headers = ["Support-Team", "Environment", "AppCatID", "Author"]

    columns = [
        # NOTE: _Region intentionally NOT exported
        "AwsAccountId","Id","GeneratorId","RuleName","Title","Description",
        "Types","ProductArn","CompanyName","ProductName","Severity.Label","Severity.Original",
        "Compliance.Status","Workflow.Status","RecordState","FirstObservedAt","LastObservedAt",
        "CreatedAt","UpdatedAt",
        # Resource flattening (from primary resource)
        "Resource.Type","Resource.Id","Resource.Partition","Resource.Region","Resource.AccountId",
        # Tag columns (exact header casing you asked for)
        "Tag.Support-Team","Tag.Environment","Tag.AppCatID","Tag.Author",
        # Keep rich JSON fields as compact JSON strings
        "Remediation.Recommendation","ProductFields","UserDefinedFields","SourceUrl",
        "Note","Vulnerabilities","Compliance.RelatedRequirements","FindingProviderFields","Confidence","Criticality"
    ]

    out = io.StringIO(newline="")
    w = csv.writer(out)
    w.writerow(columns)

    for f in findings:
        res, _idx = _primary_resource(f)
        res_tags_raw = _extract_any_tags_from_resource(res)  # lowercased keys, original punctuation preserved
        # Build a normalization map so lookups tolerate hyphens/spaces/underscores/case
        res_tags_norm = { _norm_tag_key(k): v for k, v in res_tags_raw.items() }

        row = []
        for col in columns:
            if col == "RuleName":
                row.append(derive_rule_name(f)); continue

            # Force full digits for AwsAccountId at the CSV-level
            if col == "AwsAccountId":
                row.append(_excel_safe_account(f.get("AwsAccountId", ""))); continue

            # Convenience flattening
            if col == "Severity.Label":
                row.append(f.get("Severity", {}).get("Label", "")); continue
            if col == "Severity.Original":
                row.append(f.get("Severity", {}).get("Original", "")); continue
            if col == "Compliance.Status":
                row.append(f.get("Compliance", {}).get("Status", "")); continue
            if col == "Workflow.Status":
                row.append(f.get("Workflow", {}).get("Status", "")); continue

            # Resource columns
            if col.startswith("Resource."):
                field = col.split(".",1)[1]
                if field == "AccountId":
                    row.append(_excel_safe_account(_account_id_from_resource(res, f))); continue
                row.append(res.get(field, "")); continue

            # Tag columns (case- and punctuation-insensitive lookups, header preserved)
            if col.startswith("Tag."):
                tag_key = col.split(".", 1)[1]                 # e.g., "Support-Team"
                norm_key = _norm_tag_key(tag_key)              # -> "supportteam"
                row.append(res_tags_norm.get(norm_key, ""));   continue

            # JSON-heavy
            if col in ["Types","Vulnerabilities","Compliance.RelatedRequirements"]:
                row.append(json_safe(f.get(col, []))); continue
            if col in ["ProductFields","UserDefinedFields","Remediation.Recommendation","FindingProviderFields","Note"]:
                if "." in col and col not in f:
                    row.append(json_safe(_get(f, col, {}))); continue
                row.append(json_safe(f.get(col, {}))); continue

            # Dotted fallback
            if "." in col and col not in f:
                row.append(_get(f, col, "")); continue

            v = f.get(col, "")
            row.append(json_safe(v) if isinstance(v, (dict, list)) else v)

        w.writerow(row)

    data = out.getvalue().encode("utf-8-sig")
    out.close()
    return data

def sanitize_filename(name: str) -> str:
    name = name.strip().replace(" ", "-")
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return name[:200] if name else "securityhub_findings"

def choose_attachment_name(findings, servicename: str, rule_prefix_used: str, override: str | None) -> str:
    """
    If one rule in results -> that rule name.
    Else -> <servicename>-security_findings.csv or rule_prefix fallback.
    """
    if override:
        base = override
    else:
        names = {derive_rule_name(f) for f in findings} if findings else set()
        if len(names) == 1:
            base = list(names)[0]
        else:
            base = f"{servicename}-security_findings" if servicename else (rule_prefix_used or "securityhub_findings")
    base = sanitize_filename(base)
    return base + ("" if base.lower().endswith(".csv") else ".csv")

# -------------------- Email (sleek table + explanations only) --------------------
SMTP_HOST     = os.getenv("SMTP_HOST", "smtp-aws.loud.mogc.net")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "25"))
FROM_ADDRESS  = os.getenv("SMTP_FROM", "dummy@omb.com")
DEFAULT_TO    = os.getenv("SMTP_TO", FROM_ADDRESS)
SMTP_USER     = os.getenv("SMTP_USER", "")
SMTP_PASS     = os.getenv("SMTP_PASS", "")
SMTP_STARTTLS = (os.getenv("SMTP_STARTTLS", "").strip().lower() in ("1","true","yes"))

def send_email_with_attachment(to_address: str, file_path: str, emailbody: str, servicename: str, subject_hint: str = "", extra_html: str = "", explain_html: str = ""):
    to_address = to_address or DEFAULT_TO
    servicename_u = (servicename or "report").upper()
    emailsubject = subject_hint or f"{servicename_u} security_findings report"

    body_html = []
    body_html.append(f"<b><u>{emailsubject}</u></b><br>")
    body_html.append(f"<p>{emailbody}</p>")
    if extra_html:
        body_html.append('<div style="margin:10px 0 14px 0"></div>')
        body_html.append(extra_html)
        if explain_html:
            body_html.append(explain_html)
    body_html.append("<br><b>Regards,</b><br>BMO Cloud Operations")
    html_part = MIMEText("".join(body_html), "html")

    msg = MIMEMultipart()
    msg["From"] = FROM_ADDRESS
    msg["To"] = to_address
    msg["Subject"] = emailsubject
    cc_addr = os.getenv("SMTP_CC", "").strip()
    if cc_addr:
        msg["Cc"] = cc_addr
    msg.attach(html_part)

    # Attach CSV
    try:
        with open(file_path, "rb") as fh:
            part = MIMEBase("text", "csv")
            part.set_payload(fh.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{os.path.basename(file_path)}"')
        part.add_header("Content-Transfer-Encoding", "base64")
        msg.attach(part)
        print(f"[DEBUG] Attachment added: {file_path}")
    except FileNotFoundError:
        print(f"[ERROR] CSV file not found: {file_path}")
        return 1

    rcpts = [e.strip() for e in (to_address + ("," + cc_addr if cc_addr else "")).split(",") if e.strip()]

    socket.setdefaulttimeout(SMTP_SOCKET_TIMEOUT)
    print(f"[DEBUG] SMTP connect {SMTP_HOST}:{SMTP_PORT} starttls={SMTP_STARTTLS} timeout={SMTP_SOCKET_TIMEOUT}s")

    try:
        if SMTP_PORT == 465 and not SMTP_STARTTLS:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=SMTP_SOCKET_TIMEOUT) as server:
                if SMTP_USER and SMTP_PASS: server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(FROM_ADDRESS, rcpts, msg.as_string())
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=SMTP_SOCKET_TIMEOUT) as server:
                server.ehlo()
                if SMTP_STARTTLS:
                    try:
                        server.starttls(); server.ehlo()
                    except smtplib.SMTPException:
                        print("[WARN] STARTTLS failed or not supported; continuing without TLS.")
                if SMTP_USER and SMTP_PASS: server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(FROM_ADDRESS, rcpts, msg.as_string())
        print(f"[INFO] Email sent to {', '.join(rcpts)}")
        return 0
    except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, smtplib.SMTPTimeoutError, OSError) as e:
        print(f"[ERROR] SMTP send failed {SMTP_HOST}:{SMTP_PORT} -> {e}")
        print("Hint: If on AWS, outbound :25 may be blocked. Consider 587 with SMTP_STARTTLS=true, "
              "request AWS to unblock 25, or route via an in-VPC relay.")
        return 1

# -------------------- Lambda entry --------------------
def lambda_handler(event, context):
    # Regions
    regions = getenv_list("SECURITY_HUB_REGIONS")
    if not regions:
        regions = [os.getenv("AWS_REGION", "us-east-1")]

    # Filters (env-driven to keep your “old form”) — allow external override via event
    days_back = int(event.get("days_back", os.getenv("DAYS_BACK", 7)))
    base = make_time_filter(days_back)

    rule_title_prefix   = os.getenv("RULE_TITLE_PREFIX", "BMOASR-ConfigRule-HCOPS-").strip()
    rule_prefix         = os.getenv("RULE_PREFIX", "").strip()    # fallback if title prefix not set
    compliance_statuses = getenv_list("COMPLIANCE_STATUSES")
    workflow_statuses   = getenv_list("WORKFLOW_STATUSES")
    extras = make_optional_filters(rule_title_prefix, rule_prefix, compliance_statuses, workflow_statuses)
    filters = merge_filters(base, extras)
    logger.info("Effective filters: %s", json.dumps(filters))

    # Query
    findings = collect_findings(regions, filters)

    # Dedupe (latest per rule) — unchanged
    if getenv_bool("LATEST_PER_RULE", False):
        key_mode = os.getenv("LATEST_KEY", "GENERATOR_ID").strip().upper()
        if key_mode not in ("GENERATOR_ID", "ACCOUNT_RULE"):
            key_mode = "GENERATOR_ID"
        findings = dedupe_latest(findings, key_mode)

    # ===== Sleek summary for email (unique resources) =====
    counts, wf_list, cp_list = build_workflow_compliance_summary(findings)
    summary_html = summary_to_html(counts, wf_list, cp_list)
    explain_html = summary_explanations_html(counts, wf_list, cp_list)
    # ======================================================

    # CSV (unchanged order; Account IDs forced to full digits)
    csv_bytes = to_csv_bytes(findings)

    # Attachment name
    servicename   = os.getenv("SERVICE_NAME", "BMOASR-ConfigRule-HCOPS")
   # rule_prefix_used = rule_title_prefix or rule_prefix
    rule_prefix_used = rule_title_prefix
    csv_filename = choose_attachment_name(findings, servicename, rule_prefix_used, os.getenv("CSV_FILENAME"))
    csv_path = f"/tmp/{csv_filename}"
    with open(csv_path, "wb") as fh:
        fh.write(csv_bytes)
    print(f"[DEBUG] CSV written: {csv_path} ({len(csv_bytes)} bytes) rows={len(findings)}")

    # Email body
    email_body = os.getenv("EMAIL_BODY", f"BMOASR Security Hub Findings updated in the last {days_back} days.")

    # Send (embed: grid + explanations; NO plaintext fallback)
    rc = send_email_with_attachment(
        to_address=os.getenv("SMTP_TO", ""),     # if empty -> FROM
        file_path=csv_path,
        emailbody=email_body,
        servicename=servicename,
        subject_hint=os.getenv("EMAIL_SUBJECT", ""),
        extra_html=summary_html,
        explain_html=explain_html
    )
    if rc != 0:
        raise RuntimeError("Email send failed")

    return {
        "statusCode": 200,
        "body": json.dumps({
            "regions": regions,
            "rows": len(findings),
            "filename": os.path.basename(csv_path),
            "sent_to": os.getenv("SMTP_TO", DEFAULT_TO),
            "days_back": days_back
        })
    }
