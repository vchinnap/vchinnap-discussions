import boto3
from datetime import datetime, timezone

config = boto3.client('config')
ec2 = boto3.client('ec2')
cloudwatch = boto3.client('cloudwatch')

def lambda_handler(event, context):
    evaluations = []

    # 1. Get EC2 instances tagged with ConfigRule=True and Platform=Windows
    response = ec2.describe_instances(
        Filters=[
            {'Name': 'tag:ConfigRule', 'Values': ['True']},
            {'Name': 'tag:Platform', 'Values': ['Windows']}
        ]
    )

    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instance_id = instance['InstanceId']
            timestamp = instance['LaunchTime']  # best-effort timestamp for evaluation
            compliance_type = 'NON_COMPLIANT'
            annotation = 'Missing required CloudWatch alarms'

            # 2. Check for CloudWatch alarms for this instance
            memory_alarm = False
            disk_alarms = {'C:': False, 'D:': False, 'E:': False}

            alarms = cloudwatch.describe_alarms(AlarmTypes=['MetricAlarm'])['MetricAlarms']
            for alarm in alarms:
                dimensions = {d['Name']: d['Value'] for d in alarm.get('Dimensions', [])}
                if dimensions.get('InstanceId') != instance_id:
                    continue

                metric_name = alarm.get('MetricName')

                if metric_name == 'Memory Available Bytes':
                    memory_alarm = True
                elif metric_name == 'LogicalDisk % Free Space':
                    disk = dimensions.get('LogicalDiskName')
                    if disk in disk_alarms:
                        disk_alarms[disk] = True

            # 3. Final compliance logic
            if memory_alarm and all(disk_alarms.values()):
                compliance_type = 'COMPLIANT'
                annotation = 'All required CloudWatch alarms are present.'

            evaluations.append({
                'ComplianceResourceType': 'AWS::EC2::Instance',
                'ComplianceResourceId': instance_id,
                'ComplianceType': compliance_type,
                'Annotation': annotation,
                'OrderingTimestamp': timestamp
            })

    # 4. Submit evaluations to AWS Config
    if evaluations:
        config.put_evaluations(
            Evaluations=evaluations,
            ResultToken=event['resultToken']
        )

    return {
        'status': 'completed',
        'evaluated': len(evaluations)
    }
