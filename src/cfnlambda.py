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
