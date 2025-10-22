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
    try:
        return int(os.getenv(key, str(default)))
    except Exception:
        return default

# -------------------- Filters --------------------
def make_time_filter(days_back: int):
    return {"UpdatedAt": [{"DateRange": {"Value": days_back, "Unit": "DAYS"}}]}

def make_optional_filters(rule_title_prefix, rule_prefix, compliance_statuses, workflow_statuses):
    f = {}
    if rule_title_prefix:
        f["Title"] = [{"Value": rule_title_prefix, "Comparison": "PREFIX"}]
    elif rule_prefix:
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

# -------------------- Tag helper --------------------
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
    resources = finding.get("Resources") or []
    if not isinstance(resources, list):
        return {}, -1
    for idx, r in enumerate(resources):
        if isinstance(r, dict) and _extract_any_tags_from_resource(r):
            return r, idx
    return (resources[0], 0) if resources else ({}, -1)

def _account_id_from_resource(res: dict, finding: dict) -> str:
    if isinstance(res, dict):
        acc = res.get("AccountId") or res.get("accountId")
        if acc:
            return str(acc)
        rid = res.get("Id") or ""
        if isinstance(rid, str) and rid.startswith("arn:"):
            parts = rid.split(":")
            if len(parts) >= 6 and parts[4]:
                return parts[4]
    return str(finding.get("AwsAccountId", ""))

# -------------------- Workflow × Compliance Summary --------------------
def build_workflow_compliance_summary(findings):
    combo_to_set, workflows, compliances = {}, set(), set()
    for f in findings:
        wf = (f.get("Workflow", {}) or {}).get("Status", "") or ""
        cp = (f.get("Compliance", {}) or {}).get("Status", "") or ""
        workflows.add(wf); compliances.add(cp)
        res, _ = _primary_resource(f)
        acct = _account_id_from_resource(res, f)
        rid = res.get("Id", "")
        combo_to_set.setdefault((wf, cp), set()).add((acct, rid))
    wf_sorted = sorted(workflows)
    cp_sorted = sorted(compliances)
    counts = {k: len(v) for k, v in combo_to_set.items()}
    return counts, wf_sorted, cp_sorted

def summary_to_html(counts, workflows, compliances) -> str:
    th = 'style="padding:6px 10px;border-bottom:1px solid #e5e7eb;text-align:center;font-weight:600;"'
    td = 'style="padding:6px 10px;border-bottom:1px solid #f1f5f9;text-align:center"'
    wrap = 'style="border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;font-family:system-ui,Segoe UI,Arial;font-size:13px"'
    html = [f'<div {wrap}><table style="border-collapse:collapse;width:100%">']
    html.append("<tr><th>Workflow\\Compliance</th>")
    for c in compliances: html.append(f"<th {th}>{c}</th>")
    html.append("<th>Total</th></tr>")
    for w in workflows:
        html.append(f"<tr><td {td}><b>{w}</b></td>")
        total = 0
        for c in compliances:
            v = counts.get((w,c),0)
            html.append(f"<td {td}>{v}</td>")
            total += v
        html.append(f"<td {td}><b>{total}</b></td></tr>")
    html.append("</table></div>")
    return "".join(html)

# -------------------- CSV --------------------
def to_csv_bytes(findings):
    columns = [
        "AwsAccountId","Id","GeneratorId","RuleName","Title","Description",
        "Compliance.Status","Workflow.Status","Resource.Type","Resource.Id",
        "Resource.AccountId","Tag.AppCatID","Tag.Support-Team","Tag.Stage","Tag.Author"
    ]
    out = io.StringIO(newline="")
    w = csv.writer(out); w.writerow(columns)
    for f in findings:
        res, _ = _primary_resource(f)
        tags = _extract_any_tags_from_resource(res)
        row = [
            f.get("AwsAccountId",""), f.get("Id",""), f.get("GeneratorId",""),
            f.get("Title",""), f.get("Title",""), f.get("Description",""),
            (f.get("Compliance",{}) or {}).get("Status",""),
            (f.get("Workflow",{}) or {}).get("Status",""),
            res.get("Type",""), res.get("Id",""), _account_id_from_resource(res,f),
            tags.get("appcatid",""), tags.get("support-team",""),
            tags.get("stage",""), tags.get("author","")
        ]
        w.writerow(row)
    return out.getvalue().encode("utf-8-sig")

# -------------------- Email --------------------
def send_email_with_attachment(to, file_path, html_body):
    msg = MIMEMultipart()
    msg["From"] = os.getenv("SMTP_FROM","noreply@bmo.com")
    msg["To"] = to
    msg["Subject"] = "SecurityHub Findings Report"
    msg.attach(MIMEText(html_body,"html"))
    with open(file_path,"rb") as fh:
        part = MIMEBase("text","csv")
        part.set_payload(fh.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition",f'attachment; filename="{os.path.basename(file_path)}"')
    msg.attach(part)
    with smtplib.SMTP(os.getenv("SMTP_HOST","localhost"),int(os.getenv("SMTP_PORT","25"))) as s:
        s.sendmail(msg["From"],[to],msg.as_string())
    print(f"[INFO] Email sent to {to}")

# -------------------- Lambda Entry --------------------
def lambda_handler(event, context):
    # Get days_back dynamically
    days_back = int(event.get("days_back", os.getenv("DAYS_BACK", 7)))
    print(f"[DEBUG] days_back resolved to: {days_back}")

    # Regions
    regions = getenv_list("SECURITY_HUB_REGIONS") or [os.getenv("AWS_REGION","us-east-1")]

    filters = make_time_filter(days_back)
    findings = []  # (mock for brevity, in prod call collect_findings)
    # findings = collect_findings(regions, filters)

    # Build summary
    counts, wf_list, cp_list = build_workflow_compliance_summary(findings)
    html_summary = summary_to_html(counts, wf_list, cp_list)
    for w in wf_list:
        for c in cp_list:
            print(f"[SUMMARY] {w}/{c}: {counts.get((w,c),0)}")

    # Write CSV
    csv_bytes = to_csv_bytes(findings)
    path = f"/tmp/securityhub_findings.csv"
    with open(path,"wb") as f: f.write(csv_bytes)

    # Email report
    send_email_with_attachment(os.getenv("SMTP_TO","dummy@bmo.com"), path, html_summary)

    return {"statusCode":200,"body":json.dumps({"days_back":days_back,"rows":len(findings)})}
