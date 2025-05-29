import boto3
import os

config = boto3.client('config')
logs = boto3.client('logs')

def handler(event, context):
    rule_arn = os.environ.get("CONFIG_RULE_ARN")
    function_name = context.function_name
    log_group_name = f"/aws/lambda/{function_name}"

    if not rule_arn:
        print("❌ CONFIG_RULE_ARN not set")
        return {"status": "error", "message": "Missing CONFIG_RULE_ARN"}

    # ✅ Tags to apply
    tags_to_apply = [
        {"Key": "App", "Value": "Compliance"},
        {"Key": "Owner", "Value": "CloudOps"}
    ]

    try:
        # Apply tags to Config Rule
        config.tag_resource(ResourceArn=rule_arn, Tags=tags_to_apply)
        print(f"✅ Tags applied to {rule_arn}")
    except Exception as e:
        print(f"❌ Error tagging Config Rule: {e}")

    try:
        # Delete CloudWatch Log Group if exists
        logs.delete_log_group(logGroupName=log_group_name)
        print(f"🗑️ Log group {log_group_name} deleted")
    except logs.exceptions.ResourceNotFoundException:
        print(f"ℹ️ Log group {log_group_name} already deleted or not found")
    except Exception as e:
        print(f"❌ Error deleting log group: {e}")

    return {"status": "completed"}
