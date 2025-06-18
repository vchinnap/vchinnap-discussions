import boto3
from datetime import datetime, timezone

config = boto3.client('config')
ec2 = boto3.client('ec2')
cloudwatch = boto3.client('cloudwatch')

def lambda_handler(event, context):
    result_token = event.get('resultToken', 'TESTMODE')
    evaluations = []

    # Get EC2s with ConfigRule=True tag
    response = ec2.describe_instances(
        Filters=[
            {'Name': 'tag:ConfigRule', 'Values': ['True']}
        ]
    )

    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instance_id = instance['InstanceId']
            timestamp = instance['LaunchTime']
            image_id = instance['ImageId']

            # Detect OS from Image ID
            try:
                image_details = ec2.describe_images(ImageIds=[image_id])['Images'][0]
                ami_name = image_details.get('Name', '').lower()
            except Exception as e:
                print(f"Error retrieving image details for {image_id}: {e}")
                continue

            # Define required paths based on OS
            if 'rhel' in ami_name or 'redhat' in ami_name:
                os_flavor = 'Red Hat Enterprise Linux'
                required_paths = ['/', '/var', '/tmp', '/var/log', '/var/log/audit', '/home', '/opt', '/usr']
            elif 'amzn' in ami_name or 'amazon' in ami_name:
                os_flavor = 'Amazon Linux'
                required_paths = ['/']
            else:
                print(f"Skipping unsupported AMI: {ami_name}")
                continue

            # Normalize required paths
            required_paths = [p.rstrip('/').lower() for p in required_paths]
            path_alarms = {path: False for path in required_paths}

            # Check CloudWatch alarms
            try:
                alarms = cloudwatch.describe_alarms(AlarmTypes=['MetricAlarm'])['MetricAlarms']
                for alarm in alarms:
                    dimensions = {d['Name']: d['Value'] for d in alarm.get('Dimensions', [])}
                    if dimensions.get('InstanceId') != instance_id:
                        continue
                    if alarm.get('MetricName') == 'disk_used_percent':
                        raw_path = dimensions.get('path', '')
                        path = raw_path.rstrip('/').lower()
                        if path in path_alarms:
                            path_alarms[path] = True
            except Exception as e:
                print(f"Error retrieving alarms: {e}")
                continue

            # Compliance decision
            missing_paths = [path for path, found in path_alarms.items() if not found]
            if not missing_paths:
                compliance_type = 'COMPLIANT'
                annotation = f"{os_flavor}: All required disk_used_percent alarms are present."
            else:
                compliance_type = 'NON_COMPLIANT'
                annotation = f"{os_flavor}: Missing disk alarms for paths: {', '.join(missing_paths)}"

            # Record evaluation
            evaluations.append({
                'ComplianceResourceType': 'AWS::EC2::Instance',
                'ComplianceResourceId': instance_id,
                'ComplianceType': compliance_type,
                'Annotation': annotation,
                'OrderingTimestamp': timestamp
            })

    # Send evaluations to AWS Config
    if result_token != 'TESTMODE' and evaluations:
        config.put_evaluations(
            Evaluations=evaluations,
            ResultToken=result_token
        )

    return {
        'status': 'completed',
        'evaluated': len(evaluations)
    }
