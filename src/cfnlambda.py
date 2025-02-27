import boto3

def lambda_handler(event, context):
    config_client = boto3.client('config')
    
    remediation_configuration = {
        "ConfigRuleName": "your-config-rule",            # Replace with your AWS Config rule name
        "TargetType": "SSM_DOCUMENT",                      # Must be SSM_DOCUMENT for built-in remediation actions
        "TargetId": "AWS-PublishSNSNotification",          # Built-in remediation action for SNS notifications
        "Parameters": {
            "SNSTopicArn": {
                "StaticValue": {
                    "Values": [
                        "arn:aws:sns:us-east-1:123456789012:YourNotificationTopic"  # Replace with your SNS Topic ARN
                    ]
                }
            }
        },
        "ResourceType": "AWS::SNS::Topic",                # The resource type your rule evaluates (update if needed)
        "Automatic": True,
        "MaximumAutomaticAttempts": 3,
        "RetryAttemptSeconds": 60
    }
    
    response = config_client.put_remediation_configurations(
        RemediationConfigurations=[remediation_configuration]
    )
    
    return response




import boto3

# Initialize AWS Config client
config_client = boto3.client("config")

# AWS Config Rule Name
config_rule_name = "HCOPS-ec2-volume-in-use-check-03"

# SSM Automation Document Name
ssm_document_name = "HCOPS-ec2-volume-in-use-check-03"

# IAM Role that AWS Config will assume to execute remediation
remediation_role_arn = "arn:aws:iam::123456789012:role/MyRemediationRole"

# Attach auto-remediation with required parameters
response = config_client.put_remediation_configurations(
    RemediationConfigurations=[
        {
            "ConfigRuleName": config_rule_name,
            "TargetType": "SSM_DOCUMENT",
            "TargetId": ssm_document_name,
            "Parameters": {
                "AutomationAssumeRole": {  # ✅ Fix: Explicitly add this required parameter
                    "StaticValue": {"Values": [remediation_role_arn]}
                }
            },
            "Automatic": True,  # Enable auto-remediation
            "MaximumAutomaticAttempts": 3,
            "RetryAttemptSeconds": 30
        }
    ]
)

print(f"✅ Auto-remediation configured for Config rule: {config_rule_name}")























#########################################
import json
import boto3
import os

# Initialize AWS Config client
config_client = boto3.client('config')

def lambda_handler(event, context):
    print("Received event:", json.dumps(event))

    try:
        # Get Config Rule Name from environment variable (set in CDK TypeScript)
        config_rule_name = os.getenv('CONFIG_RULE_NAME', 'hwss-ebs-optimized-instance')

        # Fetch remediation configuration for the AWS Config Rule
        response = config_client.describe_remediation_configurations(
            ConfigRuleNames=[config_rule_name]
        )

        # Check if remediation configuration exists
        if "RemediationConfigurations" in response and response["RemediationConfigurations"]:
            remediation = response["RemediationConfigurations"][0]
            result = {
                "Config Rule": config_rule_name,
                "Automatic Remediation": remediation.get("Automatic", False),
                "Maximum Automatic Attempts": remediation.get("MaximumAutomaticAttempts", 0),
                "Target ID": remediation.get("TargetId"),
                "Target Type": remediation.get("TargetType")
            }
            print("Remediation Configuration Found:", json.dumps(result, indent=2))
            return result
        else:
            print(f"No remediation configuration found for rule: {config_rule_name}")
            return {"status": "No remediation configuration found", "Config Rule": config_rule_name}

    except Exception as e:
        error_message = f"Error retrieving remediation configuration: {str(e)}"
        print(error_message)
        return {"status": "Error", "message": error_message}


















import boto3

# Initialize AWS Config client
config_client = boto3.client("config")

# Hardcoded AWS Config Rule Name (Ensure it exists in AWS Config)
config_rule_name = "my-config-rule"

# SNS Topic ARN (Replace with your SNS ARN)
sns_topic_arn = "arn:aws:sns:us-east-1:123456789012:MyRemediationTopic"

# Attach SNS-based remediation to the AWS Config rule
response = config_client.put_remediation_configurations(
    RemediationConfigurations=[
        {
            "ConfigRuleName": config_rule_name,
            "TargetType": "SNS",
            "TargetId": sns_topic_arn,  # SNS ARN
            "Automatic": True,  # Enables auto-notification
            "MaximumAutomaticAttempts": 3,
            "RetryAttemptSeconds": 30
        }
    ]
)

print(f"✅ SNS Notification for auto-remediation configured for rule: {config_rule_name}")
