import boto3
from datetime import datetime, timezone

config = boto3.client('config')
ec2 = boto3.client('ec2')
cloudwatch = boto3.client('cloudwatch')

def lambda_handler(event, context):
    result_token = event.get('resultToken', 'TESTMODE')
    evaluations = []

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
            platform = instance.get('PlatformDetails', '')

            if platform != 'Linux/UNIX':
                continue

            # Determine OS flavor from AMI
            image_id = instance['ImageId']
            try:
                image = ec2.describe_images(ImageIds=[image_id])['Images'][0]
                ami_name = image.get('Name', '').lower()
            except Exception as e:
                print(f"Error fetching AMI for instance {instance_id}: {e}")
                continue

            if 'rhel' in ami_name or 'redhat' in ami_name:
                os_flavor = 'Red Hat Linux'
                required_paths = ['/var', '/tmp', '/var/log', '/var/log/audit', '/home', '/opt', '/usr']
            elif 'amzn' in ami_name or 'al2' in ami_name:
                os_flavor = 'Amazon Linux'
                required_paths = ['/']
            else:
                print(f"Skipping unsupported AMI: {ami_name}")
                continue

            print(f"\nEvaluating instance: {instance_id} ({os_flavor})")

            # Initialize alarm tracking per required path
            path_alarms = {path: False for path in required_paths}

            try:
                alarms = cloudwatch.describe_alarms(AlarmTypes=['MetricAlarm'])['MetricAlarms']
                for alarm in alarms:
                    alarm_name = alarm.get('AlarmName', '')
                    if instance_id not in alarm_name:
                        continue
                    if 'disk_used_percent' not in alarm.get('MetricName', ''):
                        continue

                    for path in required_paths:
                        # Normalize match: handles spacing around "MountPoint :" or "MountPoint:"
                        if f"MountPoint : {path}" in alarm_name or f"MountPoint: {path}" in alarm_name or f"MountPoint :{path}" in alarm_name:
                            path_alarms[path] = True
                            print(f"Matched alarm: {alarm_name} → path: {path}")
            except Exception as e:
                print(f"Error retrieving alarms for instance {instance_id}: {e}")
                continue

            # Step 3: Final compliance check
            missing_paths = [path for path, has_alarm in path_alarms.items() if not has_alarm]
            if not missing_paths:
                compliance_type = 'COMPLIANT'
                annotation = f"{os_flavor}: Alarms exist for all required paths (via AlarmName match)."
                print(f"Result: COMPLIANT")
            else:
                compliance_type = 'NON_COMPLIANT'
                annotation = f"{os_flavor}: Missing alarms for paths: {', '.join(missing_paths)}"
                print(f"Result: NON_COMPLIANT. Missing: {missing_paths}")

            evaluations.append({
                'ComplianceResourceType': 'AWS::EC2::Instance',
                'ComplianceResourceId': instance_id,
                'ComplianceType': compliance_type,
                'Annotation': annotation,
                'OrderingTimestamp': timestamp
            })

    # Submit evaluations to AWS Config
    if result_token != 'TESTMODE' and evaluations:
        try:
            config.put_evaluations(
                Evaluations=evaluations,
                ResultToken=result_token
            )
            print("Submitted evaluations to AWS Config")
        except Exception as e:
            print(f"Error submitting evaluations: {e}")

    return {
        'status': 'completed',
        'evaluated': len(evaluations)
    }
