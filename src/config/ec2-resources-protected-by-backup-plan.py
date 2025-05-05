import boto3
from datetime import datetime, timezone

config = boto3.client('config')
ec2 = boto3.client('ec2')
backup = boto3.client('backup')

def lambda_handler(event, context):
    result_token = event.get('resultToken', 'TESTMODE')
    evaluations = []

    # Get all EC2 instances tagged with ConfigRule=True
    response = ec2.describe_instances(
        Filters=[{'Name': 'tag:ConfigRule', 'Values': ['True']}]
    )

    # Collect all EC2 instance IDs from describe_instances
    instance_ids = []
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instance_ids.append(instance['InstanceId'])

    # Get all resources protected by backup
    protected_ec2_ids = set()
    paginator = backup.get_paginator("list_protected_resources")
    for page in paginator.paginate():
        for resource in page['Results']:
            if resource['ResourceType'] == 'EC2':
                arn_parts = resource['ResourceArn'].split('/')
                if len(arn_parts) > 1:
                    protected_ec2_ids.add(arn_parts[-1])

    # Evaluate each instance
    for instance_id in instance_ids:
        compliance_type = 'COMPLIANT' if instance_id in protected_ec2_ids else 'NON_COMPLIANT'
        annotation = 'EC2 instance is protected by a backup plan.' if compliance_type == 'COMPLIANT' else 'EC2 instance is NOT protected by any backup plan.'

        evaluations.append({
            'ComplianceResourceType': 'AWS::EC2::Instance',
            'ComplianceResourceId': instance_id,
            'ComplianceType': compliance_type,
            'Annotation': annotation,
            'OrderingTimestamp': datetime.now(timezone.utc)
        })

    # Send evaluations back to Config
    config.put_evaluations(
        Evaluations=evaluations,
        ResultToken=result_token
    )
