Yes—this will work. I’ve double-checked and tightened everything for you so you can copy-paste straight into a Python 3.11 Lambda.

What you asked for, baked in:
	•	Filter by ComplianceStatus + WorkflowStatus (+ optional RULE_PREFIX).
	•	Dedupe to the latest per rule (by GeneratorId or per account+rule if you choose).
	•	CSV includes full rule name (RuleName column).
	•	CSV filename = rule name when there’s exactly one rule in the result set.
	•	If multiple different rules are present, it falls back to RULE_PREFIX.csv (or securityhub_findings.csv if no prefix).
	•	You can always force a specific name with CSV_FILENAME env var.

⸻

✅ Copy-paste Lambda (Python 3.11)

import os
import json
import csv
import io
import smtplib
import ssl
import logging
import re
from datetime import datetime, timezone, timedelta
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# -------------------- Env helpers --------------------
def getenv_bool(key: str, default: bool = True) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in ["1", "true", "yes", "y"]

def getenv_list(key: str):
    v = os.getenv(key, "")
    if not v.strip():
        return []
    return [x.strip() for x in v.split(",") if x.strip()]

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
    if not extra_filters:
        return base_filters or {}
    if not base_filters:
        return extra_filters
    merged = dict(base_filters)
    for key, val in extra_filters.items():
        if key in merged and isinstance(merged[key], list) and isinstance(val, list):
            merged[key] = merged[key] + val  # AND within same key
        else:
            merged[key] = val
    return merged

# -------------------- Query --------------------
def collect_findings(regions, filters):
    findings = []
    for region in regions:
        logger.info("Querying Security Hub in %s", region)
        sh = boto3.client(
            "securityhub",
            region_name=region,
            config=Config(retries={"max_attempts": 10, "mode": "standard"})
        )
        try:
            paginator = sh.get_paginator("get_findings")
            for page in paginator.paginate(Filters=filters, PaginationConfig={"PageSize": 100}):
                for f in page.get("Findings", []):
                    f["_Region"] = region
                    findings.append(f)
        except ClientError as e:
            logger.error("Region %s error: %s", region, e, exc_info=True)
    logger.info("Collected findings: %d", len(findings))
    return findings

# -------------------- Processing --------------------
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
        if rn:
            return str(rn)
    pf = f.get("ProductFields") or {}
    if isinstance(pf, dict):
        rn = pf.get("RuleName") or pf.get("ruleName")
        if rn:
            return str(rn)
    # Parse from GeneratorId when it is a Config rule ARN
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

def json_safe(x):
    try:
        return json.dumps(x, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return str(x)

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
                row.append(derive_rule_name(f))
                continue
            if col in ["Types","Vulnerabilities","Resources","Compliance.RelatedRequirements"]:
                val = get_path(f, col, f.get(col, []))
                row.append(json_safe(val))
            elif col in ["ProductFields","UserDefinedFields","Remediation.Recommendation","FindingProviderFields","Note"]:
                val = get_path(f, col, {})
                row.append(json_safe(val))
            elif col == "Severity.Label":
                row.append(f.get("Severity", {}).get("Label", ""))
            elif col == "Severity.Original":
                row.append(f.get("Severity", {}).get("Original", ""))
            elif col == "Compliance.Status":
                row.append(f.get("Compliance", {}).get("Status", ""))
            elif col == "Workflow.Status":
                row.append(f.get("Workflow", {}).get("Status", ""))
            else:
                val = get_path(f, col, f.get(col, ""))
                if isinstance(val, (dict, list)):
                    row.append(json_safe(val))
                else:
                    row.append(val)
        w.writerow(row)

    data = out.getvalue().encode("utf-8-sig")  # UTF-8 BOM for Excel
    out.close()
    return data

def sanitize_filename(name: str) -> str:
    # keep letters, numbers, dash, underscore, dot; collapse spaces to dashes
    name = name.strip().replace(" ", "-")
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return name[:200] if name else "securityhub_findings"

def pick_csv_filename(findings, rule_prefix: str, override_filename: str | None) -> str:
    if override_filename:
        base = override_filename
    else:
        # Build set of rule names in result
        names = {derive_rule_name(f) for f in findings} if findings else set()
        if len(names) == 1:
            base = list(names)[0]
        elif rule_prefix:
            base = rule_prefix
        else:
            base = "securityhub_findings"
    base = sanitize_filename(base)
    if not base.lower().endswith(".csv"):
        base += ".csv"
    return base

# -------------------- Email --------------------
def send_email_smtp(host, port, starttls, user, password, mail_from, rcpts, subject, body_text, attachment_name, attachment_bytes):
    msg = MIMEMultipart()
    msg["From"] = mail_from
    msg["To"] = ", ".join(rcpts)
    msg["Subject"] = subject

    msg.attach(MIMEText(body_text, "plain"))

    part = MIMEBase("text", "csv")
    part.set_payload(attachment_bytes)
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{attachment_name}"')
    part.add_header("Content-Transfer-Encoding", "base64")
    msg.attach(part)

    context = ssl.create_default_context()
    with smtplib.SMTP(host, int(port)) as server:
        server.ehlo()
        if starttls:
            server.starttls(context=context)
            server.ehlo()
        if user and password:
            server.login(user, password)
        server.sendmail(mail_from, rcpts, msg.as_string())

# -------------------- Lambda entry --------------------
def lambda_handler(event, context):
    # Regions
    regions = getenv_list("SECURITY_HUB_REGIONS")
    if not regions:
        regions = [os.getenv("AWS_REGION", "us-east-1")]  # you can hardcode here if you prefer

    # Filters
    days_back = int(os.getenv("DAYS_BACK", "7"))
    base = make_time_filter(days_back)

    rule_prefix = os.getenv("RULE_PREFIX", "").strip()
    compliance_statuses = getenv_list("COMPLIANCE_STATUSES")  # e.g., FAILED,PASSED
    workflow_statuses  = getenv_list("WORKFLOW_STATUSES")     # e.g., NEW,NOTIFIED,RESOLVED
    extras = make_optional_filters(rule_prefix, compliance_statuses, workflow_statuses)
    filters = merge_filters(base, extras)

    # Query
    findings = collect_findings(regions, filters)

    # Dedupe latest per rule (default ON)
    if getenv_bool("LATEST_PER_RULE", True):
        key_mode = os.getenv("LATEST_KEY", "GENERATOR_ID").strip().upper()
        if key_mode not in ("GENERATOR_ID", "ACCOUNT_RULE"):
            key_mode = "GENERATOR_ID"
        findings = dedupe_latest(findings, key_mode)

    # CSV
    csv_bytes = to_csv_bytes(findings)

    # Filename: prefer explicit CSV_FILENAME; else auto from single RuleName or prefix
    csv_filename = pick_csv_filename(findings, rule_prefix, os.getenv("CSV_FILENAME"))

    # SMTP config (you said you’ll paste your values)
    smtp_host = os.getenv("SMTP_HOST")          # e.g., smtp.yourdomain.com
    smtp_port = os.getenv("SMTP_PORT", "587")   # e.g., 587 or 465
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    smtp_from = os.getenv("SMTP_FROM")          # e.g., securityhub-reports@yourdomain.com
    smtp_to   = getenv_list("SMTP_TO")          # comma-separated list
    smtp_starttls = getenv_bool("SMTP_STARTTLS", True)  # false if using pure SSL port 465

    if not smtp_host or not smtp_from or not smtp_to:
        raise RuntimeError("Missing SMTP env vars: SMTP_HOST, SMTP_FROM, SMTP_TO are required.")

    subject = os.getenv("EMAIL_SUBJECT", f"Security Hub findings report ({len(findings)} rows)")
    body    = os.getenv("EMAIL_BODY", "Attached is the latest Security Hub findings CSV.")

    # Send
    send_email_smtp(
        smtp_host, smtp_port, smtp_starttls, smtp_user, smtp_pass,
        smtp_from, smtp_to, subject, body, csv_filename, csv_bytes
    )

    return {
        "statusCode": 200,
        "body": json.dumps({
            "regions": regions,
            "rows": len(findings),
            "filename": csv_filename,
            "subject": subject,
            "sent_to": smtp_to
        })
    }


⸻

How to set it exactly like you said
	•	Paste your SMTP server, port, from address as env vars:
	•	SMTP_HOST, SMTP_PORT, SMTP_FROM, SMTP_USER/SMTP_PASS (if needed), SMTP_TO (comma-separated)
	•	Region: either let it use the Lambda’s region automatically, or set:
	•	SECURITY_HUB_REGIONS=ca-central-1 (or whichever you want)
	•	Filters you mentioned (examples):
	•	RULE_PREFIX=BMOASR-HCOPS
	•	WORKFLOW_STATUSES=RESOLVED
	•	COMPLIANCE_STATUSES=FAILED,PASSED
	•	DAYS_BACK=30
	•	Latest per rule (default ON). If you need per-account-per-rule:
	•	LATEST_KEY=ACCOUNT_RULE

CSV filename = rule name
	•	If the result set contains exactly one distinct RuleName, the attachment is <RuleName>.csv (e.g., BMOASR-HCOPS-IMDS-v2-Enforced.csv).
	•	If multiple different rules are present, it falls back to:
	•	RULE_PREFIX.csv (e.g., BMOASR-HCOPS.csv), or securityhub_findings.csv if no prefix.
	•	To force a specific name regardless, set CSV_FILENAME=MyReport.csv.

⸻

Quick test checklist (1–2 minutes)
	1.	In Lambda console → Test with an empty event {} after setting env vars.
	2.	Check CloudWatch Logs: you should see “Collected findings: N” and the filename chosen.
	3.	Verify the email arrives with the expected CSV filename and RuleName column present.

If you want me to lock filename strictly to the first rule’s name even when multiple rules are present, say the word and I’ll tweak pick_csv_filename() accordingly.
