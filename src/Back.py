import boto3

logs = boto3.client('logs')

log_group_name = f"/aws/lambda/{context.function_name}"

try:
    logs.delete_log_group(logGroupName=log_group_name)
    print(f"✅ Deleted log group: {log_group_name}")
except logs.exceptions.ResourceNotFoundException:
    print(f"ℹ️ Log group not found: {log_group_name}")
