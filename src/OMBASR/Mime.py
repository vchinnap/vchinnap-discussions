import os
import json
import csv
import io
import smtplib
import ssl
import logging
import re
import socket
from datetime import datetime, timezone, timedelta
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
    try: return int(os.getenv(key, str(default)))
    except Exception: return default

# -------------------- Filters --------------------
def make_time_filter(days_back: int):
    now = datetime.now(timezone.utc)
    since = (now - timedelta(days=days_back)).isoformat()
    return {"UpdatedAt": [{"DateRange": {"Start": since, "End": now.isoformat()}}]}

def make_optional_filters(rule_prefix, compliance_statuses, workflow_statuses):
    f = {}
    if rule_prefix:
        f["GeneratorId"] = [{"Value": rule_prefix, "Comparison": "CONTAINS"}]
    if compliance_statuses:
        f["ComplianceStatus"] = [{"Value": s, "Comparison": "EQUALS"} for s in compliance_statuses]
    if workflow_statuses:
        f["WorkflowStatus"] = [{"Value": s, "Comparison": "EQUALS"} for s in workflow_statuses]
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
    # Prefer explicit names if present
    udf = f.get("UserDefinedFields") or {}
    if isinstance(udf, dict):
        rn = udf.get("RuleName")
        if rn: return str(rn)
    pf = f.get("ProductFields") or {}
    if isinstance(pf, dict):
        rn = pf.get("RuleName") or pf.get("ruleName")
        if rn: return str(rn)
    # Derive from GeneratorId
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
        if not prev:
            latest[key] = f
        else:
            prev_dt = parse_dt(prev.get("UpdatedAt", "")) or datetime.min.replace(tzinfo=timezone.utc)
            if cur_dt > prev_dt:
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
                f["_Region"] = region
                out.append(f)
                if max_findings and len(out) >= max_findings:
                    return out
            if max_pages and page_count >= max_pages:
                break
    except (ClientError, EndpointConnectionError, ReadTimeoutError, ConnectTimeoutError) as e:
        logger.error("Region %s query error: %s", region, e, exc_info=True)
    return out

def collect_findings(regions, filters):
    page_size    = getenv_int("PAGE_SIZE", 100)    # up to 100
    max_pages    = getenv_int("MAX_PAGES", 0)      # 0 = no cap
    max_findings = getenv_int("MAX_FINDINGS", 0)   # 0 = no cap
    max_workers  = getenv_int("MAX_REGION_WORKERS", min(4, len(regions) or 1))

    allf = []
    with ThreadPoolExecutor(max_workers=max_workers) as exe:
        futs = {exe.submit(_collect_region_findings, r, filters, page_size, max_pages, max_findings): r for r in regions}
        for fut in as_completed(futs):
            r = futs[fut]
            try:
                res = fut.result()
                allf.extend(res)
            except Exception as e:
                logger.error("Region %s worker failed: %s", r, e, exc_info=True)
    logger.info("Collected findings total: %d", len(allf))
    return allf

# -------------------- CSV --------------------
def json_safe(x):
    try: return json.dumps(x, ensure_ascii=False, separators=(",", ":"))
    except Exception: return str(x)

def to_csv_bytes(findings):
    columns = [
        "_Region","AwsAccountId","Id","GeneratorId","RuleName","Title","Description",
        "Types","ProductArn","CompanyName","ProductName","Severity.Label","Severity.Original",
        "Compliance.Status","Workflow.Status","RecordState","FirstObservedAt","LastObservedAt",
        "CreatedAt","UpdatedAt","Resources","Remediation.Recommendation","ProductFields",
        "UserDefinedFields","SourceUrl","Note","Vulnerabilities","Compliance.RelatedRequirements",
        "FindingProviderFields","Confidence","Criticality"
    ]

    def get_path(d, path, default=""):
        cur = d
        for p in path.split("."):
            if isinstance(cur, dict) and p in cur:
                cur = cur[p]
            else:
                return default
        return cur

    out = io.StringIO(newline="")
    w = csv.writer(out)
    w.writerow(columns)

    for f in findings:
        row = []
        for col in columns:
            if col == "RuleName":
                row.append(derive_rule_name(f)); continue
            if col in ["Types","Vulnerabilities","Resources","Compliance.RelatedRequirements"]:
                val = get_path(f, col, f.get(col, [])); row.append(json_safe(val)); continue
            if col in ["ProductFields","UserDefinedFields","Remediation.Recommendation","FindingProviderFields","Note"]:
                val = get_path(f, col, {}); row.append(json_safe(val)); continue
            if col == "Severity.Label":
                row.append(f.get("Severity", {}).get("Label", "")); continue
            if col == "Severity.Original":
                row.append(f.get("Severity", {}).get("Original", "")); continue
            if col == "Compliance.Status":
                row.append(f.get("Compliance", {}).get("Status", "")); continue
            if col == "Workflow.Status":
                row.append(f.get("Workflow", {}).get("Status", "")); continue
            val = get_path(f, col, f.get(col, ""))
            row.append(json_safe(val) if isinstance(val, (dict, list)) else val)
        w.writerow(row)

    data = out.getvalue().encode("utf-8-sig")  # Excel-friendly UTF-8
    out.close()
    return data

def sanitize_filename(name: str) -> str:
    name = name.strip().replace(" ", "-")
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return name[:200] if name else "securityhub_findings"

# If *one* rule: name the CSV after the rule; else mirror your screenshot style: hcops-<servicename>-orr.csv
def choose_attachment_name(findings, servicename: str, rule_prefix: str, override: str | None) -> str:
    if override:
        base = override
    else:
        names = {derive_rule_name(f) for f in findings} if findings else set()
        if len(names) == 1:
            base = list(names)[0]  # single rule → exact name
        else:
            base = f"hcops-{servicename}-orr" if servicename else (rule_prefix or "securityhub_findings")
    base = sanitize_filename(base)
    return base + ("" if base.lower().endswith(".csv") else ".csv")

# -------------------- Email (screenshot style) --------------------
SMTP_HOST     = os.getenv("SMTP_HOST", "smtp-aws.loud.mogc.net")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "25"))
FROM_ADDRESS  = os.getenv("SMTP_FROM", "dummy@omb.com")
DEFAULT_TO    = os.getenv("SMTP_TO", FROM_ADDRESS)
SMTP_USER     = os.getenv("SMTP_USER", "")
SMTP_PASS     = os.getenv("SMTP_PASS", "")
SMTP_STARTTLS = (os.getenv("SMTP_STARTTLS", "").strip().lower() in ("1","true","yes"))

def send_email_with_attachment(to_address: str, file_path: str, emailbody: str, servicename: str, subject_hint: str = ""):
    """
    Matches your function signature/style.
    Sends HTML body + CSV attachment. Port 25, NO STARTTLS by default.
    """
    to_address = to_address or DEFAULT_TO
    region_name = os.getenv("AWS_REGION", "ca-central-1")
    servicename_u = (servicename or "report").upper()
    emailsubject = subject_hint or f"{servicename_u} ORR Reporting data for MOR Sandbox {region_name}"

    # Build HTML body similar to your screenshot
    body_html = []
    body_html.append(f"<b><u>{emailsubject}</u></b><br>")
    body_html.append(f"<p>{emailbody}</p>")
    body_html.append("<br><b>Regards,</b><br>BMO Cloud Operation")
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

    # Recipients (To + Cc)
    rcpts = [e.strip() for e in (to_address + ("," + cc_addr if cc_addr else "")).split(",") if e.strip()]

    # Send over port 25 with short timeout and no STARTTLS by default
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
              "or request AWS to remove the block, or route via an in-VPC relay.")
        return 1

# -------------------- Lambda entry --------------------
def lambda_handler(event, context):
    # Regions
    regions = getenv_list("SECURITY_HUB_REGIONS")
    if not regions:
        regions = [os.getenv("AWS_REGION", "us-east-1")]

    # Filters
    days_back = getenv_int("DAYS_BACK", 7)
    base = make_time_filter(days_back)

    rule_prefix        = os.getenv("RULE_PREFIX", "").strip()
    compliance_statuses= getenv_list("COMPLIANCE_STATUSES")
    workflow_statuses  = getenv_list("WORKFLOW_STATUSES")
    extras = make_optional_filters(rule_prefix, compliance_statuses, workflow_statuses)
    filters = merge_filters(base, extras)
    logger.info("Effective filters: %s", json.dumps(filters))

    # Query
    findings = collect_findings(regions, filters)

    # Dedupe (latest per rule)
    if getenv_bool("LATEST_PER_RULE", True):
        key_mode = os.getenv("LATEST_KEY", "GENERATOR_ID").strip().upper()
        if key_mode not in ("GENERATOR_ID", "ACCOUNT_RULE"):
            key_mode = "GENERATOR_ID"
        findings = dedupe_latest(findings, key_mode)

    # CSV bytes
    csv_bytes = to_csv_bytes(findings)

    # Decide attachment name:
    servicename = os.getenv("SERVICE_NAME", "ec2")  # used in subject + fallback filename
    csv_filename = choose_attachment_name(findings, servicename, rule_prefix, os.getenv("CSV_FILENAME"))
    csv_path = f"/tmp/{csv_filename}"
    with open(csv_path, "wb") as fh:
        fh.write(csv_bytes)
    print(f"[DEBUG] CSV written: {csv_path} ({len(csv_bytes)} bytes) rows={len(findings)}")

    # Email body text (you can change)
    email_body = os.getenv("EMAIL_BODY", "Result of ORR… (auto-generated Security Hub findings report).")

    # Send (like your screenshot call)
    rc = send_email_with_attachment(
        to_address=os.getenv("SMTP_TO", ""),     # if empty, it sends to FROM
        file_path=csv_path,
        emailbody=email_body,
        servicename=servicename,
        subject_hint=os.getenv("EMAIL_SUBJECT", "")  # optional override
    )
    if rc != 0:
        raise RuntimeError("Email send failed")

    return {
        "statusCode": 200,
        "body": json.dumps({
            "regions": regions,
            "rows": len(findings),
            "filename": os.path.basename(csv_path),
            "sent_to": os.getenv("SMTP_TO", DEFAULT_TO)
        })
    }
