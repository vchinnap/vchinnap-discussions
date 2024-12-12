import boto3
import json
import logging

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize SSM client
ssm_client = boto3.client('ssm')


def evaluate_compliance(instance_id):
    """
    Check if the SSM Agent is running on the instance.
    """
    try:
        # Use describe_instance_information with correct filters
        response = ssm_client.describe_instance_information(
            Filters=[
                {
                    'Key': 'InstanceIds',  # Correct Key for filtering by instance IDs
                    'Values': [instance_id]  # Pass instance ID as a list
                }
            ]
        )
        
        # Check if any instance information is returned
        if len(response['InstanceInformationList']) > 0:
            # Extract PingStatus to verify agent status
            agent_status = response['InstanceInformationList'][0]['PingStatus']
            logger.info(f"SSM Agent status for {instance_id}: {agent_status}")
            return "Compliant" if agent_status == "Online" else "Noncompliant"
        else:
            logger.warning(f"No information found for instance {instance_id}")
            return "Noncompliant"

    except Exception as e:
        logger.error(f"Error checking SSM Agent status for instance {instance_id}: {e}")
        return "Noncompliant"


def lambda_handler(event, context):
    """
    AWS Lambda entry point.
    """
    try:
        # First parse the outer JSON
        invoking_event = json.loads(event['invokingEvent'])
        
        # Parse the inner stringified JSON
        config = invoking_event['configurationItem']
        instance_id = config['resourceId']
        
        if not instance_id:
            raise ValueError("InstanceID is missing in the configuration item.")
        
        # Evaluate compliance
        compliance = evaluate_compliance(instance_id)
        annotation = "SSM Agent is running" if compliance == "Compliant" else "SSM Agent is not running"
        
        return {
            'compliance_type': compliance,
            'annotation': annotation
        }
    
    except Exception as e:
        logger.error(f"Error in lambda_handler: {e}")
        return {
            'compliance_type': "Noncompliant",
            'annotation': "Error Evaluating Compliance. Check Logs for details."
        }
