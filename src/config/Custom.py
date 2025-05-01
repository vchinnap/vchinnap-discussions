import boto3
from datetime import datetime, timezone

config = boto3.client('config')
ec2 = boto3.client('ec2')
cloudwatch = boto3.client('cloudwatch')

def lambda_handler(event, context):
    result_token = event.get('resultToken', 'TESTMODE')
    evaluations = []

    # Get all EC2s with ConfigRule=True tag
    response = ec2.describe_instances(
        Filters=[
            {'Name': 'tag:ConfigRule', 'Values': ['True']}
        ]
    )

    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instance_id = instance['InstanceId']
            timestamp = instance['LaunchTime']

            # ✅ Filter only Windows instances (real platform, not tag)
            platform = instance.get('Platform', 'linux').lower()
            if platform != 'windows':
                continue

            # Default state: assume non-compliant
            compliance_type = 'NON_COMPLIANT'
            annotation_parts = []

            # 1. Check alarms
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

            # 2. Build annotation message
            if not memory_alarm:
                annotation_parts.append("Missing memory alarm")

            missing_disks = [disk for disk, found in disk_alarms.items() if not found]
            if missing_disks:
                annotation_parts.append(f"Missing disk alarms for: {', '.join(missing_disks)}")

            if not annotation_parts:
                compliance_type = 'COMPLIANT'
                annotation = "All required CloudWatch alarms are present."
            else:
                annotation = "; ".join(annotation_parts)

            # 3. Append result
            evaluations.append({
                'ComplianceResourceType': 'AWS::EC2::Instance',
                'ComplianceResourceId': instance_id,
                'ComplianceType': compliance_type,
                'Annotation': annotation,
                'OrderingTimestamp': timestamp
            })

    # 4. Submit to AWS Config
    if result_token != 'TESTMODE' and evaluations:
        config.put_evaluations(
            Evaluations=evaluations,
            ResultToken=result_token
        )

    return {
        'status': 'completed',
        'evaluated': len(evaluations)
    }
