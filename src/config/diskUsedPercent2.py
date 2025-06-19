import boto3
from datetime import datetime

config = boto3.client('config')
ec2 = boto3.client('ec2')
cloudwatch = boto3.client('cloudwatch')

def lambda_handler(event, context):
    print("Lambda execution started")

    result_token = event.get('resultToken', 'TESTMODE')
    evaluations = []
    ami_cache = {}

    try:
        response = ec2.describe_instances(
            Filters=[{'Name': 'tag:ConfigRule', 'Values': ['True']}]
        )
    except Exception as e:
        print(f"Error fetching EC2 instances: {e}")
        return

    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instance_id = instance['InstanceId']
            timestamp = instance['LaunchTime']
            image_id = instance['ImageId']
            print(f"\nWorking on instance: {instance_id}, ImageId: {image_id}")

            # Resolve AMI name
            if image_id in ami_cache:
                ami_name = ami_cache[image_id]
            else:
                try:
                    image = ec2.describe_images(ImageIds=[image_id])['Images'][0]
                    ami_name = image.get('Name', '').lower()
                    ami_cache[image_id] = ami_name
                except Exception as e:
                    print(f"Error retrieving AMI name for {image_id}: {e}")
                    continue

            print(f"AMI Name: {ami_name}")

            # Determine OS and paths
            if 'rhel' in ami_name or 'redhat' in ami_name:
                os_flavor = 'Red Hat'
                required_paths = ['/', '/var', '/tmp', '/var/log', '/var/log/audit', '/home', '/opt', '/usr']
            elif 'amzn' in ami_name or 'al2' in ami_name:
                os_flavor = 'Amazon Linux'
                required_paths = ['/']
            else:
                print(f"Skipping unsupported OS for instance: {instance_id}")
                continue

            print(f"Required paths: {required_paths}")
            path_alarms = {path: False for path in required_paths}

            # Get only disk_used_percent alarms
            try:
                all_alarms = cloudwatch.describe_alarms(AlarmTypes=['MetricAlarm'])['MetricAlarms']
                disk_alarms = [alarm for alarm in all_alarms if alarm.get('MetricName') == 'disk_used_percent']
                print(f"Found {len(disk_alarms)} disk_used_percent alarms")
            except Exception as e:
                print(f"Failed to fetch CloudWatch alarms: {e}")
                continue

            for alarm in disk_alarms:
                alarm_name = alarm.get('AlarmName')
                dimensions = {d['Name']: d['Value'] for d in alarm.get('Dimensions', [])}
                alarm_instance = dimensions.get('InstanceId')
                alarm_path = dimensions.get('path')

                print(f"Alarm: {alarm_name}")
                print(f"  InstanceId: {alarm_instance}")
                print(f"  Path: {alarm_path}")

                if not alarm_instance or alarm_instance != instance_id:
                    continue

                if alarm_path in path_alarms:
                    path_alarms[alarm_path] = True
                    print(f"  Matched path: {alarm_path}")
                else:
                    print(f"  Path '{alarm_path}' not in required list")

            # Evaluate result
            missing_paths = [path for path, found in path_alarms.items() if not found]
            if not missing_paths:
                compliance_type = 'COMPLIANT'
                annotation = f"{os_flavor}: All required disk_used_percent alarms are present."
            else:
                compliance_type = 'NON_COMPLIANT'
                annotation = f"{os_flavor}: Missing alarms for: {', '.join(missing_paths)}"

            print(f"RESULT: Instance {instance_id} → {compliance_type} — {annotation}")

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
            print("Evaluations submitted to AWS Config")
        except Exception as e:
            print(f"Error submitting evaluations: {e}")

    return {
        'status': 'completed',
        'evaluated': len(evaluations)
    }
