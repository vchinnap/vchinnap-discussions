import json
import boto3

config = boto3.client('config')
backup = boto3.client('backup')

def lambda_handler(event, context):
    invoking_event = json.loads(event['invokingEvent'])
    rule_parameters = json.loads(event.get('ruleParameters', '{}'))
    response_token = event.get('resultToken', 'NoToken')

    ec2_instance_id = invoking_event['configurationItem']['resourceId']
    
    try:
        backup_plans = backup.list_protected_resources()
        protected_instance_ids = {resource['resourceArn'].split("/")[-1] for resource in backup_plans['results']}

        compliance_type = "COMPLIANT" if ec2_instance_id in protected_instance_ids else "NON_COMPLIANT"

        config.put_evaluations(
            Evaluations=[
                {
                    'ComplianceResourceType': 'AWS::EC2::Instance',
                    'ComplianceResourceId': ec2_instance_id,
                    'ComplianceType': compliance_type,
                    'OrderingTimestamp': invoking_event['configurationItem']['configurationItemCaptureTime']
                }
            ],
            ResultToken=response_token
        )
        
        return {"message": f"Instance {ec2_instance_id} evaluated as {compliance_type}"}
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return {"error": str(e)}
