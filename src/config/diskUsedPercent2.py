import boto3
from datetime import datetime, timezone

config = boto3.client('config')
ec2 = boto3.client('ec2')
cloudwatch = boto3.client('cloudwatch')

def lambda_handler(event, context):
    result_token = event.get('resultToken', 'TESTMODE')
    evaluations = []

    print("Starting evaluation of EC2 instances tagged with ConfigRule=True")

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

            print(f"\nFound instance: {instance_id} | Platform: {platform}")

            if platform != 'Linux/UNIX':
                print(f"Skipping non-Linux instance: {instance_id}")
                continue

            # Determine OS flavor
            image_id = instance['ImageId']
            try:
                image = ec2.describe_images(ImageIds=[image_id])['Images'][0]
                ami_name = image.get('Name', '').lower()
                print(f"AMI Name for {instance_id}: {ami_name}")
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

            print(f"OS Flavor Detected: {os_flavor}")
            print(f"Required mount paths: {required_paths}")

            path_alarms = {path: False for path in required_paths}
            alarm_names = []

            try:
                alarms = cloudwatch.describe_alarms(AlarmTypes=['MetricAlarm'])['MetricAlarms']
                print(f"Total alarms fetched from CloudWatch: {len(alarms)}")

                for alarm in alarms:
                    alarm_name = alarm.get('AlarmName', '')
                    metric_name = alarm.get('MetricName', '')

                    if instance_id not in alarm_name:
                        continue
                    if 'disk_used_percent' not in metric_name:
                        continue

                    for path in required_paths:
                        if (
                            f"MountPoint : {path}" in alarm_name or
                            f"MountPoint:{path}" in alarm_name or
                            f"MountPoint :{path}" in alarm_name
                        ):
                            path_alarms[path] = True
                            alarm_names.append(alarm_name)
                            print(f"Matched alarm: {alarm_name} → path: {path}")
            except Exception as e:
                print(f"Error retrieving alarms for instance {instance_id}: {e}")
                continue

            print(f"Total matched alarms for instance {instance_id}: {len(alarm_names)}")
            for a in alarm_names:
                print(f"- {a}")

            missing_paths = [path for path, has_alarm in path_alarms.items() if not has_alarm]

            if not missing_paths:
                compliance_type = 'COMPLIANT'
                annotation = f"{os_flavor}: Alarms exist for all required paths (via AlarmName match)."
                print(f"Result: COMPLIANT for {instance_id}")
            else:
                compliance_type = 'NON_COMPLIANT'
                annotation = f"{os_flavor}: Missing alarms for paths: {', '.join(missing_paths)}"
                print(f"Result: NON_COMPLIANT for {instance_id} → Missing: {missing_paths}")

            evaluations.append({
                'ComplianceResourceType': 'AWS::EC2::Instance',
                'ComplianceResourceId': instance_id,
                'ComplianceType': compliance_type,
                'Annotation': annotation,
                'OrderingTimestamp': timestamp
            })

    if result_token != 'TESTMODE' and evaluations:
        try:
            print(f"\nSubmitting {len(evaluations)} evaluations to AWS Config...")
            config.put_evaluations(Evaluations=evaluations, ResultToken=result_token)
            print("Successfully submitted evaluations.")
        except Exception as e:
            print(f"Error submitting evaluations to AWS Config: {e}")

    print("Evaluation complete.")
    return {
        'status': 'completed',
        'evaluated': len(evaluations)
    }
