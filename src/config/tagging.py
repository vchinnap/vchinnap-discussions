import boto3

config = boto3.client('config')

def handler(event, context):
    try:
        # Extract rule name from the event payload
        rule_name = event['detail']['requestParameters']['configRuleName']
        region = event['region']
        account_id = event['account']

        # Build the ARN of the config rule
        config_rule_arn = f"arn:aws:config:{region}:{account_id}:config-rule/{rule_name}"

        # Define your desired tags
        tags = [
            {'Key': 'Environment', 'Value': 'Production'},
            {'Key': 'ManagedBy', 'Value': 'EventBridge-Lambda'}
        ]

        # Apply the tags
        config.tag_resource(ResourceArn=config_rule_arn, Tags=tags)
        print(f"✅ Successfully tagged Config Rule: {rule_name}")

    except Exception as e:
        print(f"❌ Tagging failed: {e}")
