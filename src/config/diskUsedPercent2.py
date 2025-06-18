import boto3
from datetime import datetime

config = boto3.client('config')
ec2 = boto3.client('ec2')
cloudwatch = boto3.client('cloudwatch')

def lambda_handler(event, context):
    print("Lambda execution started")

    result_token = event.get('resultToken', 'TESTMODE')
    evaluations = []

    print("Fetching EC2 instances tagged with ConfigRule=True...")
    response = ec2.describe_instances(
        Filters=[{'Name': 'tag:ConfigRule', 'Values': ['True']}]
    )

    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instance_id = instance['InstanceId']
            timestamp = instance['LaunchTime']
            image_id = instance['ImageId']

            print(f"Working on instance: {instance_id}, AMI: {image_id}")

            # Get OS type
            try:
                image = ec2.describe_images(ImageIds=[image_id])['Images'][0]
                ami_name = image.get('Name', '').lower()
                print(f"AMI name: {ami_name}")
            except Exception as e:
                print(f"Could not retrieve AMI name: {e}")
                continue

            if 'rhel' in ami_name or 'redhat' in ami_name:
                os_flavor = 'Red Hat'
                required_paths = ['/', '/var', '/tmp', '/var/log', '/var/log/audit', '/home', '/opt', '/usr']
            elif 'amzn' in ami_name or 'al2' in ami_name:
                os_flavor = 'Amazon Linux'
                required_paths = ['/']
            else:
                print("Skipping unsupported OS type")
                continue

            print(f"Required paths: {required_paths}")
            path_alarms = {path: False for path in required_paths}

            # Filter only relevant alarms upfront
            try:
                all_alarms = cloudwatch.describe_alarms(AlarmTypes=['MetricAlarm'])['MetricAlarms']
                disk_alarms = [alarm for alarm in all_alarms if alarm.get('MetricName') == 'disk_used_percent']
                print(f"Found {len(disk_alarms)} disk_used_percent alarms.")
            except Exception as e:
                print(f"Failed to fetch alarms: {e}")
                continue

            for alarm in disk_alarms:
                dimensions = {d['Name']: d['Value'] for d in alarm.get('Dimensions', [])}
                alarm_instance = dimensions.get('InstanceId')
                alarm_path = dimensions.get('path')

                if not alarm_instance:
                    print(f"Skipping alarm {alarm.get('AlarmName')} — missing InstanceId")
                    continue

                if alarm_instance != instance_id:
                    continue

                print(f"Alarm {alarm.get('AlarmName')} → InstanceId: {alarm_instance}, Path: {alarm_path}")

                if alarm_path in path_alarms:
                    path_alarms[alarm_path] = True
                    print(f"Matched path: {alarm_path}")
                else:
                    print(f"Path {alarm_path} not in required list")

            missing = [p for p, found in path_alarms.items() if not found]
            if not missing:
                compliance_type = 'COMPLIANT'
                annotation = f"{os_flavor}: All required disk alarms are present."
            else:
                compliance_type = 'NON_COMPLIANT'
                annotation = f"{os_flavor}: Missing disk alarms for: {', '.join(missing)}"

            print(f"RESULT: {instance_id} → {compliance_type}")

            evaluations.append({
                'ComplianceResourceType': 'AWS::EC2::Instance',
                'ComplianceResourceId': instance_id,
                'ComplianceType': compliance_type,
                'Annotation': annotation,
                'OrderingTimestamp': timestamp
            })

    if result_token != 'TESTMODE' and evaluations:
        try:
            config.put_evaluations(
                Evaluations=evaluations,
                ResultToken=result_token
            )
            print(" Evaluations submitted to AWS Config")
        except Exception as e:
            print(f"Failed to submit evaluations: {e}")

    return {
        'status': 'completed',
        'evaluated': len(evaluations)
    }
