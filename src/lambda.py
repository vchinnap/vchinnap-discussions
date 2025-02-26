import json
import boto3
import os

# Initialize AWS clients
ssm_client = boto3.client('ssm')
sns_client = boto3.client('sns')

# Get environment variables set in CDK
SNS_TOPIC_ARN = os.getenv('SNS_TOPIC_ARN', 'arn:aws:sns:us-east-1:123456789012:default-topic')
SSM_DOCUMENT_NAME = os.getenv('SSM_DOCUMENT_NAME', 'Your-SSM-Document-Name')

def lambda_handler(event, context):
    try:
        print("Received event: ", json.dumps(event))

        # Extract EC2 instance ID from AWS Config event
        invoking_event = json.loads(event["invokingEvent"])
        instance_id = invoking_event["configurationItem"]["resourceId"]

        # Start SSM Automation to remediate EC2 instance
        response = ssm_client.start_automation_execution(
            DocumentName=SSM_DOCUMENT_NAME,
            Parameters={"InstanceId": [instance_id]}
        )

        execution_id = response["AutomationExecutionId"]
        message = f"Remediation triggered for {instance_id}. SSM Execution ID: {execution_id}"

        # Send notification to SNS
        sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=message,
            Subject="EBS Optimization Remediation Triggered"
        )

        return {"status": "Remediation started", "execution_id": execution_id}

    except Exception as e:
        error_message = f"Error in remediation: {str(e)}"
        print(error_message)
        sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=error_message,
            Subject="EBS Optimization Remediation Failed"
        )
        return {"status": "Error", "error": str(e)}
