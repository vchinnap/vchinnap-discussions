import boto3
import json
from datetime import datetime, timezone

config = boto3.client('config')
ec2 = boto3.client('ec2')
cloudwatch = boto3.client('cloudwatch')

def check_metric_exists(instance_id):
    try:
        metrics = cloudwatch.list_metrics(
            Namespace='HCOPS/ADF',
            MetricName='disk_used_percent',
            Dimensions=[
                {'Name': 'InstanceId', 'Value': instance_id}
            ]
        ).get('Metrics', [])
        return bool(metrics)
    except Exception as e:
        print(f"⚠️ Error checking metric for {instance_id}: {e}")
        return False

def lambda_handler(event, context):
    result_token = event.get('resultToken', 'TESTMODE')
    evaluations = []

    try:
        instances = ec2.describe_instances(
            Filters=[{'Name': 'tag:ConfigRule', 'Values': ['True']}]
        )
    except Exception as e:
        print(f"❌ Error fetching EC2 instances: {e}")
        return

    instance_ids = []
    instance_map = {}

    for reservation in instances['Reservations']:
        for instance in reservation['Instances']:
            instance_id = instance['InstanceId']
            platform = instance.get('PlatformDetails', '')
            timestamp = instance['LaunchTime']

            if platform != 'Linux/UNIX':
                continue

            image_id = instance.get('ImageId')
            try:
                image = ec2.describe_images(ImageIds=[image_id])['Images'][0]
                ami_name = image.get('Name', '').lower()
            except Exception as e:
                print(f"❌ Error fetching AMI for {instance_id}: {e}")
                continue

            if 'rhel' in ami_name or 'redhat' in ami_name:
                os_flavor = 'Red Hat Linux'
                required_paths = ['/var', '/tmp', '/var/log', '/var/log/audit', '/home', '/opt', '/usr']
            elif 'amzn' in ami_name or 'al2' in ami_name:
                os_flavor = 'Amazon Linux'
                required_paths = ['/']
            else:
                print(f"⚠️ Unsupported AMI: {ami_name} for instance {instance_id}")
                continue

            instance_ids.append(instance_id)
            instance_map[instance_id] = {
                "required_paths": required_paths,
                "os_flavor": os_flavor,
                "timestamp": timestamp
            }

    if not instance_ids:
        print("ℹ️ No Linux EC2 instances found with ConfigRule=True.")
        return

    print(f"✅ Instances for evaluation: {instance_ids}")

    try:
        paginator = cloudwatch.get_paginator('describe_alarms')
        alarm_pages = paginator.paginate()
        all_alarms = []
        for page in alarm_pages:
            all_alarms.extend(page['MetricAlarms'])
    except Exception as e:
        print(f"❌ Error fetching alarms: {e}")
        return

    for instance_id in instance_ids:
        print(f"\n🔍 Checking alarms for Instance ID: {instance_id}")

        required_paths = instance_map[instance_id]['required_paths']
        os_flavor = instance_map[instance_id]['os_flavor']
        timestamp = instance_map[instance_id]['timestamp']
        path_status = {path: False for path in required_paths}

        metric_available = check_metric_exists(instance_id)

        for alarm in all_alarms:
            if alarm.get('MetricName') != 'disk_used_percent':
                continue

            dims = {d['Name']: d['Value'] for d in alarm.get('Dimensions', [])}
            if dims.get('InstanceId') != instance_id:
                continue

            path = dims.get('path')
            if path in required_paths:
                path_status[path] = True
                print(f"✅ Matched: {alarm['AlarmName']} | Path: {path}")
                print(json.dumps(alarm, indent=2, default=str))

        missing_paths = [p for p, present in path_status.items() if not present]

        if not metric_available:
            compliance_type = 'NON_COMPLIANT'
            annotation = f"{os_flavor}: disk_used_percent metric not found for instance {instance_id}"
        elif missing_paths:
            compliance_type = 'NON_COMPLIANT'
            annotation = f"{os_flavor}: Alarms missing for paths: {', '.join(missing_paths)}"
        else:
            compliance_type = 'COMPLIANT'
            annotation = f"{os_flavor}: All required disk_used_percent alarms are present."

        print(f"📌 Evaluation: {instance_id} → {compliance_type}")
        print(f"📝 Annotation: {annotation}")

        evaluations.append({
            'ComplianceResourceType': 'AWS::EC2::Instance',
            'ComplianceResourceId': instance_id,
            'ComplianceType': compliance_type,
            'Annotation': annotation,
            'OrderingTimestamp': timestamp
        })

    # Submit results to AWS Config
    if result_token != 'TESTMODE' and evaluations:
        try:
            config.put_evaluations(
                Evaluations=evaluations,
                ResultToken=result_token
            )
            print("✅ Submitted evaluations to AWS Config")
        except Exception as e:
            print(f"❌ Error submitting evaluations: {e}")

    return {
        'status': 'completed',
        'evaluated': len(evaluations)
    }
