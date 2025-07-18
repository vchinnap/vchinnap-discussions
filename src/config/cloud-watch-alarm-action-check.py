import boto3
from datetime import datetime, timezone

config = boto3.client('config')
ec2 = boto3.client('ec2')
cloudwatch = boto3.client('cloudwatch')

def lambda_handler(event, context):
    result_token = event.get('resultToken', 'TESTMODE')
    evaluations = []

    # Get EC2 instances with ConfigRule=True tag
    try:
        instances = ec2.describe_instances(
            Filters=[{'Name': 'tag:ConfigRule', 'Values': ['True']}]
        )
    except Exception as e:
        print(f"❌ Error fetching EC2 instances: {e}")
        return

    try:
        all_alarms = cloudwatch.describe_alarms(AlarmTypes=['MetricAlarm'])['MetricAlarms']
    except Exception as e:
        print(f"❌ Error fetching CloudWatch alarms: {e}")
        return

    for reservation in instances['Reservations']:
        for instance in reservation['Instances']:
            instance_id = instance['InstanceId']
            timestamp = instance['LaunchTime']

            platform_details = instance.get('PlatformDetails', '')
            platform = instance.get('Platform', 'linux').lower()

            # Default metric requirements
            metric_requirements = {}
            disk_path_requirements = {}

            if platform == 'windows':
                metric_requirements = {
                    'CPUUtilization': False,
                    'Memory Available Bytes': False,
                    'LogicalDisk % Free Space C:': False,
                    'LogicalDisk % Free Space D:': False,
                    'LogicalDisk % Free Space E:': False,
                    'StatusCheckFailed': False
                }

            elif platform_details == 'Linux/UNIX':
                metric_requirements = {
                    'CPUUtilization': False,
                    'mem_used_percent': False,
                    'disk_used_percent': False,  # ✅ Global check added
                    'StatusCheckFailed': False
                }

                # Detect OS flavor and set disk paths
                image_id = instance.get('ImageId')
                try:
                    image = ec2.describe_images(ImageIds=[image_id])['Images'][0]
                    ami_name = image.get('Name', '').lower()
                except Exception as e:
                    print(f"❌ Error fetching AMI for {instance_id}: {e}")
                    continue

                if 'rhel' in ami_name or 'redhat' in ami_name:
                    required_paths = ['/var', '/tmp', '/var/log', '/var/log/audit', '/home', '/opt', '/usr']
                elif 'amzn' in ami_name or 'al2' in ami_name:
                    required_paths = ['/']
                else:
                    print(f"⚠️ Unsupported AMI: {ami_name} for instance {instance_id}")
                    continue

                for path in required_paths:
                    disk_path_requirements[path] = False

            else:
                continue  # Skip unsupported OS

            # Match alarms for this instance
            for alarm in all_alarms:
                dims = {d['Name']: d['Value'] for d in alarm.get('Dimensions', [])}
                if dims.get('InstanceId') != instance_id:
                    continue

                metric = alarm.get('MetricName')
                path = dims.get('path')
                disk = dims.get('LogicalDiskName')

                # Determine metric key
                if metric == 'LogicalDisk % Free Space':
                    metric_key = f"{metric} {disk}" if disk else None
                elif metric == 'disk_used_percent':
                    metric_key = 'disk_used_percent'  # ✅ global key
                else:
                    metric_key = metric

                has_alarm = bool(alarm.get('AlarmActions'))
                has_ok = bool(alarm.get('OKActions'))
                has_insufficient = bool(alarm.get('InsufficientDataActions'))
                all_actions_present = has_alarm and has_ok and has_insufficient

                if metric_key in metric_requirements and all_actions_present:
                    metric_requirements[metric_key] = True

                if platform_details == 'Linux/UNIX' and metric == 'disk_used_percent' and path in disk_path_requirements:
                    if all_actions_present:
                        disk_path_requirements[path] = "OK"
                    else:
                        disk_path_requirements[path] = "MISSING_ACTIONS"

            # Evaluate compliance
            missing_metrics = [m for m, ok in metric_requirements.items() if not ok]
            missing_paths = []
            missing_actions_paths = []

            for path, status in disk_path_requirements.items():
                if status is False:
                    missing_paths.append(path)
                elif status == "MISSING_ACTIONS":
                    missing_actions_paths.append(path)

            if missing_metrics or missing_paths or missing_actions_paths:
                compliance_type = 'NON_COMPLIANT'
                messages = []
                if missing_metrics:
                    messages.append(f"Missing alarms or actions for: {', '.join(missing_metrics)}")
                if missing_paths:
                    messages.append(f"Missing disk alarms for paths: {', '.join(missing_paths)}")
                if missing_actions_paths:
                    messages.append(f"Disk alarms missing actions for paths: {', '.join(missing_actions_paths)}")
                annotation = " | ".join(messages)
            else:
                compliance_type = 'COMPLIANT'
                annotation = "All required alarms with actions are present."

            evaluations.append({
                'ComplianceResourceType': 'AWS::EC2::Instance',
                'ComplianceResourceId': instance_id,
                'ComplianceType': compliance_type,
                'Annotation': annotation,
                'OrderingTimestamp': timestamp
            })

    # Submit to AWS Config
    if result_token != 'TESTMODE' and evaluations:
        try:
            config.put_evaluations(Evaluations=evaluations, ResultToken=result_token)
            print("✅ Evaluation results submitted to AWS Config.")
        except Exception as e:
            print(f"❌ Failed to submit evaluations: {e}")

    return {
        'status': 'completed',
        'evaluated': len(evaluations)
    }
