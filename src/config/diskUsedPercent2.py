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

            # Detect OS from AMI name
            try:
                image_details = ec2.describe_images(ImageIds=[image_id])['Images'][0]
                ami_name = image_details.get('Name', '').lower()
            except Exception as e:
                print(f"❌ Error retrieving image details for {image_id}: {e}")
                continue

            # Define OS-specific required paths
            if 'rhel' in ami_name or 'redhat' in ami_name:
                os_flavor = 'Red Hat Enterprise Linux'
                required_paths = ['/', '/var', '/tmp', '/var/log', '/var/log/audit', '/home', '/opt', '/usr']
            elif 'amzn' in ami_name or 'al2' in ami_name:
                os_flavor = 'Amazon Linux'
                required_paths = ['/']
            else:
                print(f"ℹ️ Skipping unsupported AMI: {ami_name}")
                continue

            path_alarms = {path: False for path in required_paths}

            # Fetch and match alarms
            try:
                alarms = cloudwatch.describe_alarms(AlarmTypes=['MetricAlarm'])['MetricAlarms']
                for alarm in alarms:
                    dimensions = {d['Name']: d['Value'] for d in alarm.get('Dimensions', [])}
                    metric_name = alarm.get('MetricName')
                    namespace = alarm.get('Namespace')

                    if dimensions.get('InstanceId') != instance_id:
                        continue

                    if metric_name == 'disk_used_percent':
                        raw_path = dimensions.get('path', '')
                        normalized_path = raw_path.rstrip('/')

                        print(f"[DEBUG] Instance: {instance_id}, Namespace: {namespace}, Metric: {metric_name}, Path: '{raw_path}' -> '{normalized_path}'")

                        if normalized_path in path_alarms:
                            path_alarms[normalized_path] = True

            except Exception as e:
                print(f"❌ Error retrieving alarms: {e}")
                continue

            # Evaluate compliance
            missing_paths = [path for path, found in path_alarms.items() if not found]

            if not missing_paths:
                compliance_type = 'COMPLIANT'
                annotation = f"{os_flavor}: All required disk_used_percent alarms are present."
            else:
                compliance_type = 'NON_COMPLIANT'
                annotation = f"{os_flavor}: Missing disk alarms for paths: {', '.join(missing_paths)}"

            print(f"[RESULT] Instance {instance_id} is {compliance_type}. {annotation}")

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
