import boto3
from datetime import datetime

config = boto3.client('config')
ec2 = boto3.client('ec2')
cloudwatch = boto3.client('cloudwatch')

def lambda_handler(event, context):
    print("🔍 Lambda started...")

    result_token = event.get('resultToken', 'TESTMODE')
    evaluations = []

    print("🔹 Describing EC2 instances with tag ConfigRule=True")
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
            platform = instance.get('PlatformDetails', '')

            print(f"\n📦 Instance: {instance_id}, Platform: {platform}, ImageId: {image_id}")

            # Detect OS flavor
            try:
                image = ec2.describe_images(ImageIds=[image_id])['Images'][0]
                ami_name = image.get('Name', '').lower()
                print(f"🔍 AMI name: {ami_name}")
            except Exception as e:
                print(f"❌ Error retrieving AMI name: {e}")
                continue

            if 'rhel' in ami_name or 'redhat' in ami_name:
                os_flavor = 'Red Hat'
                required_paths = ['/', '/var', '/tmp', '/var/log', '/var/log/audit', '/home', '/opt', '/usr']
            elif 'amzn' in ami_name or 'al2' in ami_name:
                os_flavor = 'Amazon Linux'
                required_paths = ['/']
            else:
                print("⚠️ Skipping unsupported OS flavor")
                continue

            print(f"✅ OS: {os_flavor}, Required paths: {required_paths}")
            path_alarms = {path: False for path in required_paths}

            try:
                alarms = cloudwatch.describe_alarms(AlarmTypes=['MetricAlarm'])['MetricAlarms']
                print(f"🔔 Total CloudWatch alarms found: {len(alarms)}")
            except Exception as e:
                print(f"❌ Error retrieving alarms: {e}")
                continue

            for alarm in alarms:
                metric_name = alarm.get('MetricName')
                dimensions = {d['Name']: d['Value'] for d in alarm.get('Dimensions', [])}
                alarm_instance = dimensions.get('InstanceId')
                alarm_path = dimensions.get('path') or 'N/A'

                print(f"🔍 Alarm: {alarm.get('AlarmName')}")
                print(f"    → Metric: {metric_name}")
                print(f"    → InstanceId: {alarm_instance}")
                print(f"    → Path: {alarm_path}")

                if alarm_instance != instance_id:
                    print("    ⛔ Skipped: instance ID doesn't match.")
                    continue

                if metric_name != 'disk_used_percent':
                    print("    ⛔ Skipped: metric is not disk_used_percent.")
                    continue

                if alarm_path in path_alarms:
                    path_alarms[alarm_path] = True
                    print(f"    ✅ Matched required path: {alarm_path}")
                else:
                    print(f"    ❌ Path '{alarm_path}' not in required list")

            missing_paths = [path for path, found in path_alarms.items() if not found]
            if not missing_paths:
                compliance_type = 'COMPLIANT'
                annotation = f"{os_flavor}: All required disk_used_percent alarms are present."
            else:
                compliance_type = 'NON_COMPLIANT'
                annotation = f"{os_flavor}: Missing disk alarms for paths: {', '.join(missing_paths)}"

            print(f"[RESULT] Instance {instance_id} is {compliance_type} — {annotation}")

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
            print("✅ PutEvaluations sent to AWS Config")
        except Exception as e:
            print(f"❌ Error submitting evaluations: {e}")

    return {
        'status': 'completed',
        'evaluated': len(evaluations)
    }
