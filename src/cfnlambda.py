import json
import boto3
import os

config_client = boto3.client('config')
sns_client = boto3.client('sns')

# Get environment variables for Config Rule and SNS Topic ARN
CONFIG_RULE_NAME = os.getenv('CONFIG_RULE_NAME', 'default-config-rule')
SNS_TOPIC_ARN = os.getenv('SNS_TOPIC_ARN', 'arn:aws:sns:us-east-1:123456789012:RemediationTopic')

def lambda_handler(event, context):
    print("Received event:", json.dumps(event))

    try:
        # Extract resource details from AWS Config event
        invoking_event = json.loads(event.get("invokingEvent", "{}"))
        instance_id = invoking_event.get("configurationItem", {}).get("resourceId", "UnknownInstance")

        # Apply AWS Config Remediation Configuration using SNS
        response = config_client.put_remediation_configuration(
            ConfigRuleName=CONFIG_RULE_NAME,
            TargetId=SNS_TOPIC_ARN,  # SNS Topic ARN
            TargetType="SNS",  # Set SNS as the remediation target
            Automatic=True,
            MaximumAutomaticAttempts=3,
            RetryAttemptSeconds=60
        )

        # Send a notification to SNS about remediation action
        sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=f"Remediation triggered for {instance_id} under rule {CONFIG_RULE_NAME}",
            Subject="AWS Config Remediation Triggered"
        )

        print("Remediation Configuration Applied:", json.dumps(response))
        return {"status": "Success", "message": f"Remediation configured for {instance_id}"}

    except Exception as e:
        error_message = f"Error applying remediation: {str(e)}"
        print(error_message)
        sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=error_message,
            Subject="AWS Config Remediation Failed"
        )
        return {"status": "Error", "message": str(e)}






import json
import boto3
import os

config_client = boto3.client('config')

def lambda_handler(event, context):
    print("Received event:", json.dumps(event))

    try:
        # Extracting AWS Config rule name and resource ID
        config_rule_name = os.getenv('CONFIG_RULE_NAME', 'hwss-ebs-optimized-instance')  # Read from env variable
        invoking_event = json.loads(event.get("invokingEvent", "{}"))
        instance_id = invoking_event.get("configurationItem", {}).get("resourceId", "UnknownInstance")

        # Define the remediation configuration dynamically
        response = config_client.put_remediation_configuration(
            ConfigRuleName=config_rule_name,
            TargetId="arn:aws:ssm:us-east-1:123456789012:automation-definition/MySSMDocument:1",  # Replace with actual SSM Document ARN
            TargetType="SSM_DOCUMENT",
            Parameters={
                "InstanceId": {
                    "ResourceValue": {
                        "Value": "RESOURCE_ID"
                    }
                }
            },
            Automatic=True,
            MaximumAutomaticAttempts=3,
            RetryAttemptSeconds=60
        )

        print("Remediation Configuration Applied:", json.dumps(response))
        return {"status": "Success", "message": f"Remediation configured for {instance_id}"}

    except Exception as e:
        print(f"Error applying remediation: {str(e)}")
        return {"status": "Error", "message": str(e)}
