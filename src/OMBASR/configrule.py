import boto3, os
from datetime import datetime, timezone

config = boto3.client("config")
ec2 = boto3.client("ec2")

# --------- Tag constants ---------
# Required tags for this rule
CFG_TAG_KEY  = "ConfigRule"
CFG_TAG_VAL  = "True"

PERSIST_TAG_KEY = "ResourcePersistency"
PERSIST_TAG_VAL = "persistent"

# L2 support team tag + allowed values (CSV)
L2_TAG_KEY = os.getenv("L2_TAG_KEY", "Support-Team-L2")
L2_ALLOWED_LIST = {
    v.strip()
    for v in os.getenv("L2_ALLOWED_LIST", "").split(",")
    if v.strip()
}


def _tag_val(tags, key):
    for t in tags or []:
        if t.get("Key") == key:
            return t.get("Value")
    return None


def _iter_instances_filtered_by_l2():
    """
    Iterate EC2 instances, but only yield those whose L2 support team
    is in the configured allowed list (L2_ALLOWED_LIST).
    If L2_ALLOWED_LIST is empty, treat as 'no L2 filter' (yield all).
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

                # If we have an explicit L2 list and this instance's L2 is not in it, skip
                if L2_ALLOWED_LIST and l2_val not in L2_ALLOWED_LIST:
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

        cfg_val    = _tag_val(tags, CFG_TAG_KEY)
        persist_val = _tag_val(tags, PERSIST_TAG_KEY)

        # ---- Compliance logic ----
        if cfg_val == CFG_TAG_VAL and persist_val == PERSIST_TAG_VAL:
            comp = "COMPLIANT"
            anno = (
                f"Required tags present: "
                f"{CFG_TAG_KEY}={CFG_TAG_VAL}, {PERSIST_TAG_KEY}={PERSIST_TAG_VAL}."
            )
        else:
            comp = "NON_COMPLIANT"

            # As per your ask: if tags are missing/incorrect, keep / show only ConfigRule=True in annotation
            if cfg_val != CFG_TAG_VAL:
                anno = (
                    f"Required tag '{CFG_TAG_KEY}'='{CFG_TAG_VAL}' "
                    f"is missing or incorrect."
                )
            else:
                # ConfigRule=True is present, but other tags (like ResourcePersistency) are not OK
                anno = (
                    f"Instance has '{CFG_TAG_KEY}'='{CFG_TAG_VAL}', "
                    f"but required tagging standard is not fully met."
                )

        evals.append({
            "ComplianceResourceType": "AWS::EC2::Instance",
            "ComplianceResourceId": iid,
            "ComplianceType": comp,
            "Annotation": anno[:256],
            "OrderingTimestamp": inst.get("LaunchTime", now),
        })

    if result_token != "TESTMODE" and evals:
        for batch in _chunks(evals, 100):
            config.put_evaluations(Evaluations=batch, ResultToken=result_token)

    return {"status": "ok", "evaluated": len(evals)}
