import boto3, os
from datetime import datetime, timezone

config = boto3.client("config")
ec2 = boto3.client("ec2")

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
    "AppOps-L2"
}

# L2 tag key (hard-coded)
L2_TAG_KEY = "Support-Team-L2"


def _tag_val(tags, key):
    for t in tags or []:
        if t.get("Key") == key:
            return t.get("Value")
    return None


def _iter_instances_filtered():
    """
    Yield only instances where:
      - Support-Team-L2 tag is in ALLOWED_L2_TEAMS
      - ResourcePersistency == 'persistent'
    """
    token = None

    while True:
        params = {}
        if token:
            params["NextToken"] = token

        resp = ec2.describe_instances(**params)

        for r in resp.get("Reservations", []):
            for inst in r.get("Instances", []):
                tags = inst.get("Tags", [])

                l2_val      = _tag_val(tags, L2_TAG_KEY)
                persist_val = _tag_val(tags, PERSIST_TAG_KEY)

                # Skip if L2 team not allowed
                if l2_val not in ALLOWED_L2_TEAMS:
                    continue

                # Skip if ResourcePersistency is not 'persistent'
                if persist_val != PERSIST_TAG_VAL:
                    continue

                # Passed filters → this instance will be evaluated
                yield inst

        token = resp.get("NextToken")
        if not token:
            break


def _chunks(items, n=100):
    for i in range(0, len(items), n):
        yield items[i:i+n]


def lambda_handler(event, context):
    result_token = event.get("resultToken", "TESTMODE")
    now = datetime.now(timezone.utc)
    evals = []

    # Only filtered instances (L2 + persistent) are evaluated
    for inst in _iter_instances_filtered():
        iid  = inst["InstanceId"]
        tags = inst.get("Tags", [])

        cfg_val = _tag_val(tags, CFG_TAG_KEY)

        # --------- Compliance: ONLY ConfigRule matters ----------
        if cfg_val == CFG_TAG_VAL:
            comp = "COMPLIANT"
            anno = f"Required tag '{CFG_TAG_KEY}'='{CFG_TAG_VAL}' is present."
        else:
            comp = "NON_COMPLIANT"
            anno = (
                f"Required tag '{CFG_TAG_KEY}'='{CFG_TAG_VAL}' "
                f"is missing or incorrect."
            )

        evals.append({
            "ComplianceResourceType": "AWS::EC2::Instance",
            "ComplianceResourceId": iid,
            "ComplianceType": comp,
            "Annotation": anno[:256],
            "OrderingTimestamp": inst.get("LaunchTime", now)
        })

    # ------------------- Send to AWS Config -------------------
    if result_token != "TESTMODE" and evals:
        for batch in _chunks(evals, 100):
            config.put_evaluations(Evaluations=batch, ResultToken=result_token)

    return {"status": "ok", "evaluated": len(evals)}
