import boto3
from datetime import datetime, timezone

config = boto3.client('config')
ec2 = boto3.client('ec2')
backup = boto3.client('backup')

def lambda_handler(event, context):
    result_token = event.get('resultToken', 'TESTMODE')
    evaluations = []

    # Get all EC2s tagged with ConfigRule=True
    response = ec2.describe_instances(
        Filters=[{'Name': 'tag:ConfigRule', 'Values': ['True']}]
    )

    # Fetch all protected resources from backup
    protected_resources = set()
    paginator = backup.get_paginator('list_protected_resources')
    for page in paginator.paginate(ResourceType='EC2'):
        for resource in page['Results']:
            protected_resources.add(resource['ResourceArn'])

    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instance_id = instance['InstanceId']
            timestamp = instance['LaunchTime']
            instance_arn = f"arn:aws:ec2:{ec2.meta.region_name}:{instance['OwnerId']}:instance/{instance_id}"

            compliance_type = 'NON_COMPLIANT'
            annotation = "EC2 instance is not protected by any backup plan"

            if instance_arn in protected_resources:
                compliance_type = 'COMPLIANT'
                annotation = "EC2 instance is protected by a backup plan"

            evaluations.append({
                'ComplianceResourceType': 'AWS::EC2::Instance',
                'ComplianceResourceId': instance_id,
                'ComplianceType': compliance_type,
                'Annotation': annotation,
                'OrderingTimestamp': timestamp
            })

    if result_token != 'TESTMODE' and evaluations:
        config.put_evaluations(
            Evaluations=evaluations,
            ResultToken=result_token
        )

    return {
        'status': 'completed',
        'evaluated': len(evaluations)
    }
