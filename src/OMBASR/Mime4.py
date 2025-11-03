import os
import json
import csv
import io
import smtplib
import ssl
import logging
import re
import socket
from datetime import datetime, timezone
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    # Security Hub supports DateRange for UpdatedAt (Finding updated time)
    return {"UpdatedAt": [{"DateRange": {"Value": days_back, "Unit": "DAYS"}}]}

def make_optional_filters_title_prefix(rule_title_prefix, compliance_statuses=None, workflow_statuses=None):
    """
    Title PREFIX filter + optional compliance/workflow/record state.
    """
    f = {}
    if rule_title_prefix:
        f["Title"] = [{"Value": rule_title_prefix, "Comparison": "PREFIX"}]

    if compliance_statuses:
        f["ComplianceStatus"] = [{"Value": s, "Comparison": "EQUALS"} for s in compliance_statuses]
    if workflow_statuses:
        f["WorkflowStatus"] = [{"Value": s, "Comparison": "EQUALS"} for s in workflow_statuses]

    record_state = os.getenv("RECORD_STATE", "ACTIVE").strip().upper()
    if record_state:
        f["RecordState"] = [{"Value": record_state, "Comparison": "EQUALS"}]
    return f

def make_note_filters(days_back: int, require_updated_by: bool = True):
    """
    Filter for note recency and (optionally) presence of UpdatedBy.
    """
    note_by_contains = os.getenv("NOTE_UPDATED_BY_CONTAINS", "@") if require_updated_by else None
    f = {
        "NoteUpdatedAt": [{"DateRange": {"Value": days_back, "Unit": "DAYS"}}]
    }
    if note_by_contains:
        f["NoteUpdatedBy"] = [{"Value": note_by_contains, "Comparison": "CONTAINS"}]
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
    def normalize(k): return k.lower().replace("-", "")
    out = {}
    if isinstance(tags_field, list):
        for t in tags_field:
            if not isinstance(t, dict):
                continue
            k = (t.get("Key") or "").strip()
            v = t.get("Value")
            if k:
                out[normalize(k)] = v
    elif isinstance(tags_field, dict):
        for k, v in tags_field.items():
            if isinstance(k, str):
                out[normalize(k)] = v
    return out

def _extract_any_tags_from_resource(res: dict):
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

def _primary_resource(finding: dict):
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

def _excel_safe_account(x) -> str:
    s = str(x or "").strip()
    if not s:
        return ""
    if s.isdigit():
        return f'="{s}"'
    return s

def _account_id_from_resource(res: dict, finding: dict) -> str:
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

# -------------------- Summary (only the slices you want) --------------------
def build_workflow_compliance_summary_only_new_failed_and_resolved_passed(findings):
    """
    Count unique resources for just:
      - NEW × FAILED
      - RESOLVED × PASSED
    """
    combos = {("NEW","FAILED"): 0, ("RESOLVED","PASSED"): 0}
    seen = set()  # uniqueness key: (accountId, resourceId, workflow, compliance)

    for f in findings:
        wf = (f.get("Workflow", {}) or {}).get("Status", "") or ""
        cp = (f.get("Compliance", {}) or {}).get("Status", "") or ""
        if (wf, cp) not in combos:
            continue

        res, _ = _primary_resource(f)
        rid = res.get("Id") or res.get("id") or "" if isinstance(res, dict) else ""
        acct = _account_id_from_resource(res, f)
        key = (acct, rid, wf, cp)
        if key not in seen and (acct or rid):
            combos[(wf, cp)] += 1
            seen.add(key)

    return {("NEW","FAILED"): combos[("NEW","FAILED")],
            ("RESOLVED","PASSED"): combos[("RESOLVED","PASSED")]}

def summary_to_html_minimal(counts) -> str:
    base_cell = "padding:6px 10px;border-bottom:1px solid #f1f5f9;text-align:center"
    th_cell   = "padding:6px 10px;border-bottom:1px solid #e5e7eb;text-align:center;font-weight:600;white-space:nowrap"
    hd_cell   = "text-align:left;padding:8px 10px;border-bottom:1px solid #e5e7eb;font-weight:700"
    wrap      = 'style="border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial;font-size:13px;color:#0f172a"'

    new_failed = counts.get(("NEW","FAILED"), 0)
    res_passed = counts.get(("RESOLVED","PASSED"), 0)
    total = new_failed + res_passed

    html = []
    html.append(f'<div {wrap}>')
    html.append('<table style="border-collapse:collapse;width:100%">')
    html.append('<tr>')
    html.append(f'<th style="{hd_cell}">Workflow \\ Compliance</th>')
    html.append(f'<th style="{th_cell}">FAILED</th>')
    html.append(f'<th style="{th_cell}">PASSED</th>')
    html.append(f'<th style="{th_cell}">TOTAL</th>')
    html.append('</tr>')
    html.append('<tr>')
    html.append(f'<td style="padding:6px 10px;border-bottom:1px solid #f1f5f9;text-align:left;font-weight:600">NEW</td>')
    html.append(f'<td style="{base_cell}">{new_failed}</td>')
    html.append(f'<td style="{base_cell}">0</td>')
    html.append(f'<td style="{base_cell}"><b>{new_failed}</b></td>')
    html.append('</tr>')
    html.append('<tr>')
    html.append(f'<td style="padding:6px 10px;border-bottom:1px solid #f1f5f9;text-align:left;font-weight:600">RESOLVED</td>')
    html.append(f'<td style="{base_cell}">0</td>')
    html.append(f'<td style="{base_cell}">{res_passed}</td>')
    html.append(f'<td style="{base_cell}"><b>{res_passed}</b></td>')
    html.append('</tr>')
    html.append('<tr>')
    html.append('<td style="padding:6px 10px;background:#f8fafc;border-top:1px solid #e5e7eb;text-align:left;font-weight:700">TOTAL</td>')
    html.append(f'<td style="padding:6px 10px;background:#f8fafc;border-top:1px solid #e5e7eb;text-align:center;font-weight:700">{new_failed}</td>')
    html.append(f'<td style="padding:6px 10px;background:#f8fafc;border-top:1px solid #e5e7eb;text-align:center;font-weight:700">{res_passed}</td>')
    html.append(f'<td style="padding:6px 10px;background:#f8fafc;border-top:1px solid #e5e7eb;text-align:center;font-weight:800">{total}</td>')
    html.append('</tr>')
    html.append('</table></div>')
    return "".join(html)

def explanations_html(counts) -> str:
    new_failed = counts.get(("NEW","FAILED"), 0)
    res_passed = counts.get(("RESOLVED","PASSED"), 0)
    items = []
    if new_failed:
        items.append(f'<li><b>NEW × FAILED</b> — {new_failed} unique resources (newly opened, non-compliant).</li>')
    if res_passed:
        items.append(f'<li><b>RESOLVED × PASSED</b> — {res_passed} unique resources (closed and compliant with a recent note update).</li>')
    if not items:
        return ""
    return '<ul style="margin:10px 0 0 18px; padding:0; color:#334155; font-size:13px">' + "".join(items) + "</ul>"

# -------------------- CSV --------------------
def to_csv_bytes(findings):
    # Tag columns you asked for (case-insensitive keying)
    tag_headers = ["Support-Team", "Environment", "AppCatID", "Author"]

    columns = [
        "RuleName",
        "Title",
        "Resource.Id",
        "Resource.Type",
        "Resource.AccountId",
        "AwsAccountId",
        "Compliance.Status",
        "Workflow.Status",
        "Severity.Label",
        "UpdatedAt",
        "CreatedAt",
        # Tags (exact header names preserved)
        "Tag.Support-Team",
        "Tag.Environment",
        "Tag.AppCatID",
        "Tag.Author",
        # Some useful JSON fields (compact)
        "ProductFields",
        "UserDefinedFields",
        "Remediation.Recommendation",
        "GeneratorId",
        "Id"
    ]

    display_columns = []
    for col in columns:
        if col == "Compliance.Status":
            display_columns.append("ComplianceStatus")
        elif col == "Workflow.Status":
            display_columns.append("WorkflowStatus")
        elif col.startswith("Tag."):
            display_columns.append(col.split(".",1)[1])  # keep exact tag header
        elif col.startswith("Resource."):
            display_columns.append(col.split(".",1)[1])
        else:
            display_columns.append(col)

    out = io.StringIO(newline="")
    w = csv.writer(out)
    w.writerow(display_columns)

    for f in findings:
        res, _idx = _primary_resource(f)
        res_tags = _extract_any_tags_from_resource(res)

        row = []
        for col in columns:
            if col == "RuleName":
                row.append(derive_rule_name(f)); continue

            if col == "AwsAccountId":
                row.append(_excel_safe_account(f.get("AwsAccountId", ""))); continue

            if col == "Severity.Label":
                row.append(f.get("Severity", {}).get("Label", "")); continue
            if col == "Compliance.Status":
                row.append(f.get("Compliance", {}).get("Status", "")); continue
            if col == "Workflow.Status":
                row.append(f.get("Workflow", {}).get("Status", "")); continue

            if col.startswith("Resource."):
                field = col.split(".",1)[1]
                if field == "AccountId":
                    row.append(_excel_safe_account(_account_id_from_resource(res, f))); continue
                row.append(res.get(field, "")); continue

            if col.startswith("Tag."):
                key_wanted = col.split(".", 1)[1].lower().replace("-", "")
                row.append(res_tags.get(key_wanted, "")); continue

            # JSON-ish dotted access
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
    if override:
        base = override
    else:
        names = {derive_rule_name(f) for f in findings} if findings else set()
        if len(names) == 1:
            base = list(names)[0]
        elif rule_prefix_used:
            base = f"{servicename}-{rule_prefix_used}-security_findings"
        else:
            base = f"{servicename}-security_findings"
    base = sanitize_filename(base)
    return base + ("" if base.lower().endswith(".csv") else ".csv")

# -------------------- Email --------------------
SMTP_HOST     = os.getenv("SMTP_HOST", "smtp-aws.hloud.mogc.net")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "25"))
FROM_ADDRESS  = os.getenv("SMTP_FROM", "operations@omb.com")
DEFAULT_TO    = os.getenv("SMTP_TO", FROM_ADDRESS)
SMTP_USER     = os.getenv("SMTP_USER", "")
SMTP_PASS     = os.getenv("SMTP_PASS", "")
SMTP_STARTTLS = (os.getenv("SMTP_STARTTLS", "").strip().lower() in ("1","true","yes"))

def send_email_with_attachment(to_address: str, file_path: str, emailbody: str, servicename: str, subject_hint: str = "", extra_html: str = "", explain_html: str = ""):
    to_address = to_address or DEFAULT_TO
    emailsubject = subject_hint or f"{(servicename or 'report')} security_findings report"

    body_html = [f"<p>{emailbody}</p>"]
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
    cc_addr = os.getenv("SMTP_CC", "vinod.chinnapati@omb.com, vinod.chinnapati@omb.com").strip()
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

    # Inputs
    days_back = int(event.get("days_back", os.getenv("DAYS_BACK", 7)))
    title_prefix = os.getenv("RULE_TITLE_PREFIX", "BMOASR-ConfigRule-HCOPS").strip()

    # --- Slice A: Title starts with BMOASR-ConfigRule-HCOPS AND Workflow=NEW AND Compliance=FAILED
    baseA = make_time_filter(days_back)
    optA  = make_optional_filters_title_prefix(
        rule_title_prefix=title_prefix,
        compliance_statuses=["FAILED"],
        workflow_statuses=["NEW"]
    )
    filtersA = merge_filters(baseA, optA)
    logger.info("Filters A (NEW×FAILED): %s", json.dumps(filtersA))

    findingsA = collect_findings(regions, filtersA)

    # --- Slice B: Title starts with ... AND Compliance != FAILED (we use PASSED) AND Workflow=RESOLVED AND NoteUpdatedAt in last days_back AND NoteUpdatedBy present
    baseB = make_time_filter(days_back)
    optB  = make_optional_filters_title_prefix(
        rule_title_prefix=title_prefix,
        compliance_statuses=["PASSED"],  # narrowed to PASSED to match email requirement
        workflow_statuses=["RESOLVED"]
    )
    noteB = make_note_filters(days_back=days_back, require_updated_by=True)
    filtersB = merge_filters(merge_filters(baseB, optB), noteB)
    logger.info("Filters B (RESOLVED×PASSED with recent note): %s", json.dumps(filtersB))

    findingsB = collect_findings(regions, filtersB)

    # Combine
    findings = findingsA + findingsB

    # Optional dedupe (off by default)
    if getenv_bool("LATEST_PER_RULE", False):
        key_mode = os.getenv("LATEST_KEY", "GENERATOR_ID").strip().upper()
        if key_mode not in ("GENERATOR_ID", "ACCOUNT_RULE"):
            key_mode = "GENERATOR_ID"
        findings = dedupe_latest(findings, key_mode)

    # Summary only for the two asked combos
    counts = build_workflow_compliance_summary_only_new_failed_and_resolved_passed(findings)
    summary_html = summary_to_html_minimal(counts)
    explain_html = explanations_html(counts)

    # CSV
    csv_bytes = to_csv_bytes(findings)
    servicename = os.getenv("SERVICE_NAME", "BMOASR-ConfigRule-HCOPS")
    csv_filename = choose_attachment_name(findings, servicename, title_prefix, os.getenv("CSV_FILENAME"))
    csv_path = f"/tmp/{csv_filename}"
    with open(csv_path, "wb") as fh:
        fh.write(csv_bytes)
    print(f"[DEBUG] CSV written: {csv_path} ({len(csv_bytes)} bytes) rows={len(findings)}")

    # Email body
    email_body = os.getenv("EMAIL_BODY", f"BMOASR Security Hub Findings in the last {days_back} days (NEW×FAILED and RESOLVED×PASSED).")

    # Send
    rc = send_email_with_attachment(
        to_address=os.getenv("SMTP_TO", ""),
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
            "rows_slice_A_new_failed": len(findingsA),
            "rows_slice_B_resolved_passed_note_recent": len(findingsB),
            "filename": os.path.basename(csv_path),
            "sent_to": os.getenv("SMTP_TO", DEFAULT_TO),
            "days_back": days_back
        })
    }
