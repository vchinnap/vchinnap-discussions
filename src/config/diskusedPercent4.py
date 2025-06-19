import boto3
import json

def lambda_handler(event, context):
    ec2 = boto3.client('ec2')
    cloudwatch = boto3.client('cloudwatch')

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
                "os_flavor": os_flavor
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
        path_status = {path: False for path in required_paths}

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
        if missing_paths:
            print(f"❌ {os_flavor} - Alarms missing for paths: {', '.join(missing_paths)}")
        else:
            print(f"✅ {os_flavor} - All required disk_used_percent alarms are present for this instance.")










import boto3
import json

def lambda_handler(event, context):
    ec2 = boto3.client('ec2')
    cloudwatch = boto3.client('cloudwatch')

    try:
        # Step 1: Get instance IDs with tag ConfigRule=True
        instances = ec2.describe_instances(
            Filters=[{'Name': 'tag:ConfigRule', 'Values': ['True']}]
        )
    except Exception as e:
        print(f"❌ Error fetching EC2 instances: {e}")
        return

    instance_ids = []
    for reservation in instances['Reservations']:
        for instance in reservation['Instances']:
            instance_ids.append(instance['InstanceId'])

    if not instance_ids:
        print("ℹ️ No instances found with tag ConfigRule=True")
        return

    print(f"✅ Found instances: {instance_ids}")

    # Step 2: Get all CloudWatch alarms
    try:
        paginator = cloudwatch.get_paginator('describe_alarms')
        alarm_pages = paginator.paginate()
        all_alarms = []
        for page in alarm_pages:
            all_alarms.extend(page['MetricAlarms'])
    except Exception as e:
        print(f"❌ Error fetching alarms: {e}")
        return

    # Step 3: Match alarms by instance ID
    for instance_id in instance_ids:
        print(f"\n🔍 Alarms for Instance ID: {instance_id}")
        print("--------------------------------------------------")
        for alarm in all_alarms:
            for dim in alarm.get('Dimensions', []):
                if dim.get('Name') == 'InstanceId' and dim.get('Value') == instance_id:
                    print(json.dumps({
                        "AlarmName": alarm.get('AlarmName'),
                        "MetricName": alarm.get('MetricName'),
                        "Namespace": alarm.get('Namespace'),
                        "Dimensions": alarm.get('Dimensions'),
                        "ComparisonOperator": alarm.get('ComparisonOperator'),
                        "Threshold": alarm.get('Threshold'),
                        "EvaluationPeriods": alarm.get('EvaluationPeriods'),
                        "StateValue": alarm.get('StateValue'),
                        "AlarmDescription": alarm.get('AlarmDescription')
                    }, indent=2))
        print("--------------------------------------------------")
