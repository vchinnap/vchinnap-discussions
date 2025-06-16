import boto3
import json

config = boto3.client('config')

def lambda_handler(event, context):
    print("📥 Event received:")
    print(json.dumps(event))

    try:
        # Extract the config rule name from the event
        rule_name = event['detail']['requestParameters']['configRule']['configRuleName']
        print(f"🔍 Config rule name: {rule_name}")

        # Get the rule ARN using DescribeConfigRules
        response = config.describe_config_rules(ConfigRuleNames=[rule_name])
        rule_arn = response['ConfigRules'][0]['ConfigRuleArn']
        print(f"📌 Found rule ARN: {rule_arn}")

        # Define tags to apply
        tags = [
            {'Key': 'Environment', 'Value': 'Production'},
            {'Key': 'Team', 'Value': 'CloudOps'}
        ]

        # Apply tags
        config.tag_resource(ResourceArn=rule_arn, Tags=tags)
        print(f"🏷️ Tags applied successfully to: {rule_arn}")

        return {
            'statusCode': 200,
            'body': f"Successfully tagged Config Rule: {rule_name}"
        }

    except Exception as e:
        print(f"❌ Error tagging Config Rule: {str(e)}")
        return {
            'statusCode': 500,
            'body': str(e)
        }
