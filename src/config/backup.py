import boto3
from datetime import datetime, timezone

# AWS clients
config = boto3.client('config')
ec2 = boto3.client('ec2')
backup = boto3.client('backup')

def get_account_id_from_arn(arn):
    # Extracts the AWS account ID from the Lambda's ARN
    return arn.split(":")[4]

def is_instance_protected(instance_arn):
    try:
        response = backup.list_recovery_points_by_resource(
            ResourceArn=instance_arn,
            MaxResults=1
        )
        return len(response.get('RecoveryPoints', [])) > 0
    except Exception as e:
        print(f"Error checking backup for {instance_arn}: {str(e)}")
        return False

def lambda_handler(event, context):
    result_token = event.get('resultToken', 'TESTMODE')
    evaluations = []

    region = boto3.session.Session().region_name
    account_id = get_account_id_from_arn(context.invoked_function_arn)

    # Get EC2 instances tagged with ConfigRule=True
    try:
        instances = ec2.describe_instances(
            Filters=[{'Name': 'tag:ConfigRule', 'Values': ['True']}]
        )
    except Exception as e:
        print(f"Error describing instances: {str(e)}")
        return

    for reservation in instances['Reservations']:
        for instance in reservation['Instances']:
            instance_id = instance['InstanceId']
            timestamp = datetime.now(timezone.utc)
            instance_arn = f"arn:aws:ec2:{region}:{account_id}:instance/{instance_id}"

            compliance_type = 'COMPLIANT' if is_instance_protected(instance_arn) else 'NON_COMPLIANT'
            annotation = "Backup recovery point exists" if compliance_type == 'COMPLIANT' else "No backup found"

            evaluations.append({
                'ComplianceResourceType': 'AWS::EC2::Instance',
                'ComplianceResourceId': instance_id,
                'ComplianceType': compliance_type,
                'Annotation': annotation,
                'OrderingTimestamp': timestamp
            })

    if evaluations:
        try:
            config.put_evaluations(Evaluations=evaluations, ResultToken=result_token)
        except Exception as e:
            print(f"Error putting evaluations: {str(e)}")
