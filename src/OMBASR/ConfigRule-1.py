import json
from datetime import datetime, timezone
import boto3

config = boto3.client("config")

# --------- Required tags ----------
CFG_TAG_KEY  = "ConfigRule"
CFG_TAG_VAL  = "True"

PERSIST_TAG_KEY = "ResourcePersistency"
PERSIST_TAG_VAL = "persistent"

# --------- HARD-CODED L2 SUPPORT TEAMS ----------
ALLOWED_L2_TEAMS = {
    "Platform-L2",
    "Compute-L2",
    "Storage-L2",
    "Network-L2",
    "AppOps-L2",
}

# L2 tag key (hard-coded)
L2_TAG_KEY = "Support-Team-L2"


def _tag(tags: dict, key: str):
    """Return a tag value from AWS Config configurationItem.tags dict."""
    if not tags:
        return None
    return tags.get(key)


def _eval_from_tags(resource_id: str, tags: dict, capture_time: str):
    """
    Tag-only decision:
      - If not persistent OR L2 not allowed -> NOT_APPLICABLE
      - Else require ConfigRule=True -> COMPLIANT/NON_COMPLIANT
    """
    persist_val = _tag(tags, PERSIST_TAG_KEY)
    l2_val      = _tag(tags, L2_TAG_KEY)
    cfg_val     = _tag(tags, CFG_TAG_KEY)

    # Out-of-scope => NOT_APPLICABLE (clears any previous result)
    if persist_val != PERSIST_TAG_VAL or not l2_val or l2_val not in ALLOWED_L2_TEAMS:
        comp = "NOT_APPLICABLE"
        anno = (
            "Out of scope for this rule. Requires "
            f"{PERSIST_TAG_KEY}='{PERSIST_TAG_VAL}' and "
            f"{L2_TAG_KEY} in {sorted(ALLOWED_L2_TEAMS)}."
        )
    else:
        if cfg_val == CFG_TAG_VAL:
            comp = "COMPLIANT"
            anno = f"Required tag '{CFG_TAG_KEY}'='{CFG_TAG_VAL}' present."
        else:
            comp = "NON_COMPLIANT"
            anno = f"Required tag '{CFG_TAG_KEY}'='{CFG_TAG_VAL}' missing or incorrect."

    # Use Config's capture timestamp if possible
    try:
        ts = datetime.fromisoformat(capture_time.replace("Z", "+00:00"))
    except Exception:
        ts = datetime.now(timezone.utc)

    return {
        "ComplianceResourceType": "AWS::EC2::Instance",
        "ComplianceResourceId": resource_id,
        "ComplianceType": comp,
        "Annotation": anno[:256],
        "OrderingTimestamp": ts,
    }


def lambda_handler(event, context):
    """
    AWS Config Custom Rule Lambda (Tag-level evaluation)
    - Trigger type: Configuration changes
    - Scope: AWS::EC2::Instance
    """
    result_token = event.get("resultToken", "TESTMODE")
    invoking = json.loads(event.get("invokingEvent", "{}"))
    msg_type = invoking.get("messageType")
    ci = invoking.get("configurationItem", {}) or {}

    # --- Normal resource change notification ---
    if msg_type == "ConfigurationItemChangeNotification":
        resource_type = ci.get("resourceType")
        resource_id   = ci.get("resourceId")
        capture_time  = ci.get("configurationItemCaptureTime") or datetime.now(timezone.utc).isoformat()
        status        = ci.get("configurationItemStatus")
        tags          = ci.get("tags", {})  # dict of tag key -> value

        if resource_type != "AWS::EC2::Instance" or not resource_id:
            return {"status": "ignored", "reason": "not an EC2 instance change"}

        # Deleted or unrecorded instance
        if status in ("ResourceDeleted", "ResourceNotRecorded"):
            eval_rec = {
                "ComplianceResourceType": "AWS::EC2::Instance",
                "ComplianceResourceId": resource_id,
                "ComplianceType": "NOT_APPLICABLE",
                "Annotation": "Resource deleted or no longer recorded.",
                "OrderingTimestamp": datetime.now(timezone.utc),
            }
        else:
            eval_rec = _eval_from_tags(resource_id, tags, capture_time)

        if result_token != "TESTMODE":
            config.put_evaluations(Evaluations=[eval_rec], ResultToken=result_token)

        return {"status": "ok", "evaluated": 1, "resource": resource_id}

    # --- Oversized payload (tags not included) ---
    if msg_type == "OversizedConfigurationItemChangeNotification":
        oi = invoking.get("configurationItemSummary", {}) or {}
        resource_type = oi.get("resourceType")
        resource_id   = oi.get("resourceId")
        if resource_type == "AWS::EC2::Instance" and resource_id and result_token != "TESTMODE":
            config.put_evaluations(
                Evaluations=[{
                    "ComplianceResourceType": "AWS::EC2::Instance",
                    "ComplianceResourceId": resource_id,
                    "ComplianceType": "INSUFFICIENT_DATA",
                    "Annotation": "Oversized CI; tags unavailable in summary.",
                    "OrderingTimestamp": datetime.now(timezone.utc),
                }],
                ResultToken=result_token
            )
        return {"status": "ok", "oversized": True, "resource": resource_id}

    # --- Other event types (periodic, snapshot, etc.) ---
    return {"status": "ignored", "reason": f"messageType={msg_type}"}
