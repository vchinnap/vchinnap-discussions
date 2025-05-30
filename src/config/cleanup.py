import boto3

logs = boto3.client('logs')
ssm = boto3.client('ssm')

def handler(event, context):
    try:
        rule_name = event['detail']['requestParameters']['configRuleName']
        lambda_name = f"{rule_name}-tags"
        log_group_name = f"/aws/lambda/{lambda_name}"
        ssm_doc_name = f"{rule_name}-ssm"

        # 🔥 Delete log group
        try:
            logs.delete_log_group(logGroupName=log_group_name)
            print(f"🧹 Deleted log group: {log_group_name}")
        except logs.exceptions.ResourceNotFoundException:
            print(f"ℹ️ Log group not found: {log_group_name}")

        # 🔥 Delete SSM document
        try:
            ssm.delete_document(Name=ssm_doc_name)
            print(f"🧹 Deleted SSM Document: {ssm_doc_name}")
        except ssm.exceptions.InvalidDocument:
            print(f"ℹ️ SSM Document not found: {ssm_doc_name}")

    except Exception as e:
        print(f"❌ Cleanup failed: {e}")
