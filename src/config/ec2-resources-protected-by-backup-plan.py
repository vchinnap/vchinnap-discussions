import boto3
from datetime import datetime, timezone

config = boto3.client('config')
ec2 = boto3.client('ec2')
backup = boto3.client('backup')

def lambda_handler(event, context):
    result_token = event.get('resultToken', 'TESTMODE')
    evaluations = []

    # Get all protected EC2 instance ARNs from backup
    protected_instance_ids = set()
    paginator = backup.get_paginator('list_protected_resources')
    for page in paginator.paginate(ResourceType='EC2'):
        for resource in page['Results']:
            # ARN format: arn:aws:ec2:<region>:<account>:instance/<instance-id>
            instance_id = resource['ResourceArn'].split('/')[-1]
            protected_instance_ids.add(instance_id)

    # Get EC2 instances tagged with ConfigRule=True
    response = ec2.describe_instances(
        Filters=[{'Name': 'tag:ConfigRule', 'Values': ['True']}]
    )

    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instance_id = instance['InstanceId']
            timestamp = instance['LaunchTime']

            if instance_id in protected_instance_ids:
                compliance_type = 'COMPLIANT'
                annotation = "EC2 instance is protected by a backup plan"
            else:
                compliance_type = 'NON_COMPLIANT'
                annotation = "EC2 instance is NOT protected by any backup plan"

            evaluations.append({
                'ComplianceResourceType': 'AWS::EC2::Instance',
                'ComplianceResourceId': instance_id,
                'ComplianceType': compliance_type,
                'Annotation': annotation,
                'OrderingTimestamp': timestamp
            })

    # Submit to AWS Config
    if result_token != 'TESTMODE' and evaluations:
        config.put_evaluations(
            Evaluations=evaluations,
            ResultToken=result_token
        )

    return {
        'status': 'completed',
        'evaluated': len(evaluations)
    }
