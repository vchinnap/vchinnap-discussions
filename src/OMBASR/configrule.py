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
# Modify this list as needed
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


def _iter_instances_filtered_by_l2():
    """
    Yield only instances where Support-Team-L2 tag matches our
    allowed L2 support team list.
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

                l2_val = _tag_val(tags, L2_TAG_KEY)

                # Skip if L2 team not in hard-coded list
                if l2_val not in ALLOWED_L2_TEAMS:
                    continue

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

    for inst in _iter_instances_filtered_by_l2():
        iid = inst["InstanceId"]
        tags = inst.get("Tags", [])

        cfg_val      = _tag_val(tags, CFG_TAG_KEY)
        persist_val  = _tag_val(tags, PERSIST_TAG_KEY)

        # ------------------- Compliance Logic -------------------
        if cfg_val == CFG_TAG_VAL and persist_val == PERSIST_TAG_VAL:
            comp = "COMPLIANT"
            anno = (
                f"Required tags present: "
                f"{CFG_TAG_KEY}={CFG_TAG_VAL}, "
                f"{PERSIST_TAG_KEY}={PERSIST_TAG_VAL}."
            )
        else:
            comp = "NON_COMPLIANT"

            # Annotation rule: show only ConfigRule=True in missing tag cases
            if cfg_val != CFG_TAG_VAL:
                anno = (
                    f"Required tag '{CFG_TAG_KEY}'='{CFG_TAG_VAL}' "
                    f"is missing or incorrect."
                )
            else:
                anno = (
                    f"Instance has '{CFG_TAG_KEY}'='{CFG_TAG_VAL}', "
                    f"but required tagging standard is not fully met."
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
