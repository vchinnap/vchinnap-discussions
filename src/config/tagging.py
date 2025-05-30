import boto3

config = boto3.client('config')

def handler(event, context):
    try:
        rule_name = event['detail']['requestParameters']['configRuleName']
        account_id = event['account']
        region = event['region']
        config_rule_arn = f"arn:aws:config:{region}:{account_id}:config-rule/{rule_name}"

        tags = [
            {'Key': 'Environment', 'Value': 'Production'},
            {'Key': 'ManagedBy', 'Value': 'EventBridge-Lambda'}
        ]

        config.tag_resource(ResourceArn=config_rule_arn, Tags=tags)
        print(f"✅ Tagged Config Rule: {rule_name}")
    except Exception as e:
        print(f"❌ Failed tagging: {e}")
