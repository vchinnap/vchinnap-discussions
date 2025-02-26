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
