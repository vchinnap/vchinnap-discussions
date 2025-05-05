import boto3
from datetime import datetime, timezone

config = boto3.client('config')
ec2 = boto3.client('ec2')
backup = boto3.client('backup')
sts = boto3.client('sts')

def lambda_handler(event, context):
    result_token = event.get('resultToken', 'TESTMODE')
    evaluations = []

    session = boto3.session.Session()
    region = session.region_name
    account_id = sts.get_caller_identity()['Account']

    # Get all EC2s with tag:ConfigRule=True
    response = ec2.describe_instances(
        Filters=[{'Name': 'tag:ConfigRule', 'Values': ['True']}]
    )

    # Get all protected resources (no filter)
    protected_arns = set()
    try:
        response = backup.list_protected_resources()
        for res in response['Results']:
            if res['ResourceType'] == 'EC2':
                protected_arns.add(res['ResourceArn'])
    except Exception as e:
        print(f"ERROR fetching protected resources: {str(e)}")

    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instance_id = instance['InstanceId']
            timestamp = datetime.now(timezone.utc)

            arn = f"arn:aws:ec2:{region}:{account_id}:instance/{instance_id}"
            compliance_type = 'COMPLIANT' if arn in protected_arns else 'NON_COMPLIANT'
            annotation = "Protected by AWS Backup" if compliance_type == 'COMPLIANT' else "Not protected by AWS Backup"

            evaluations.append({
                'ComplianceResourceType': 'AWS::EC2::Instance',
                'ComplianceResourceId': instance_id,
                'ComplianceType': compliance_type,
                'Annotation': annotation,
                'OrderingTimestamp': timestamp
            })

    if evaluations:
        config.put_evaluations(Evaluations=evaluations, ResultToken=result_token)
        
