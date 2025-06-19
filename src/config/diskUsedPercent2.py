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

            # ✅ Filter only Linux/UNIX instances
            platform_details = instance.get('PlatformDetails', '')
            if platform_details != 'Linux/UNIX':
                continue

            # Required paths
            required_paths = ['/var', '/tmp', '/var/log', '/var/log/audit', '/home', '/opt', '/usr']
            path_alarms = {path: False for path in required_paths}

            # Fetch all alarms
            alarms = cloudwatch.describe_alarms(AlarmTypes=['MetricAlarm'])['MetricAlarms']
            for alarm in alarms:
                if alarm.get('MetricName') != 'disk_used_percent':
                    continue
                dimensions = {d['Name']: d['Value'] for d in alarm.get('Dimensions', [])}
                if dimensions.get('InstanceId') != instance_id:
                    continue
                path = dimensions.get('path')
                if path in path_alarms:
                    path_alarms[path] = True

            # Check which paths are missing
            missing_paths = [path for path, found in path_alarms.items() if not found]

            if not missing_paths:
                compliance_type = 'COMPLIANT'
                annotation = "All required disk_used_percent alarms are present."
            else:
                compliance_type = 'NON_COMPLIANT'
                annotation = f"Missing disk alarms for: {', '.join(missing_paths)}"

            # Append result
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
