import boto3
from datetime import datetime, timezone

config = boto3.client('config')
ec2 = boto3.client('ec2')
cloudwatch = boto3.client('cloudwatch')

def lambda_handler(event, context):
    result_token = event.get('resultToken', 'TESTMODE')
    evaluations = []

    try:
        print("Fetching EC2 instances with tag ConfigRule=True...")
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

            print(f"\nProcessing instance: {instance_id}")
            if platform != 'Linux/UNIX':
                print(f"Skipping: Not a Linux/UNIX platform ({platform})")
                continue

            # Detect OS flavor
            image_id = instance['ImageId']
            try:
                image = ec2.describe_images(ImageIds=[image_id])['Images'][0]
                ami_name = image.get('Name', '').lower()
                print(f"AMI name: {ami_name}")
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
                print(f"Unsupported AMI: {ami_name}. Skipping instance.")
                continue

            print(f"OS Flavor: {os_flavor}")
            print("Discovering published metric paths...")

            # Step 1: Get published metric paths
            found_paths = set()
            try:
                paginator = cloudwatch.get_paginator('list_metrics')
                for page in paginator.paginate(
                    MetricName='disk_used_percent',
                    Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}]
                ):
                    for metric in page['Metrics']:
                        dims = {d['Name']: d['Value'] for d in metric['Dimensions']}
                        path = dims.get('path')
                        if path in required_paths:
                            found_paths.add(path)
                            print(f"Metric found for path: {path}")
            except Exception as e:
                print(f"Error listing metrics: {e}")
                continue

            if not found_paths:
                print("No matching metric paths published. Skipping instance.")
                continue

            # Step 2: Initialize alarm flags for found paths only
            path_alarms = {path: False for path in found_paths}
            print("Checking alarms...")

            try:
                alarms = cloudwatch.describe_alarms(AlarmTypes=['MetricAlarm'])['MetricAlarms']
                for alarm in alarms:
                    if alarm.get('MetricName') != 'disk_used_percent':
                        continue

                    dims = {d['Name']: d['Value'] for d in alarm.get('Dimensions', [])}
                    alarm_instance = dims.get('InstanceId')
                    alarm_path = dims.get('path')

                    if alarm_instance == instance_id and alarm_path in path_alarms:
                        path_alarms[alarm_path] = True
                        print(f"Alarm matched for path: {alarm_path} (AlarmName: {alarm['AlarmName']})")
            except Exception as e:
                print(f"Error retrieving alarms: {e}")
                continue

            # Step 3: Final compliance check
            missing_paths = [path for path, has_alarm in path_alarms.items() if not has_alarm]
            if not missing_paths:
                compliance_type = 'COMPLIANT'
                annotation = f"{os_flavor}: Alarms exist for all required paths."
                print("Result: COMPLIANT")
            else:
                compliance_type = 'NON_COMPLIANT'
                annotation = f"{os_flavor}: Missing alarms for paths: {', '.join(missing_paths)}"
                print(f"Result: NON_COMPLIANT. Missing alarms for: {missing_paths}")

            evaluations.append({
                'ComplianceResourceType': 'AWS::EC2::Instance',
                'ComplianceResourceId': instance_id,
                'ComplianceType': compliance_type,
                'Annotation': annotation,
                'OrderingTimestamp': timestamp
            })

    # Step 4: Submit to AWS Config
    if result_token != 'TESTMODE' and evaluations:
        try:
            print(f"Submitting {len(evaluations)} evaluations to AWS Config...")
            config.put_evaluations(Evaluations=evaluations, ResultToken=result_token)
            print("Evaluations submitted successfully.")
        except Exception as e:
            print(f"Error submitting evaluations: {e}")

    return {
        'status': 'completed',
        'evaluated': len(evaluations)
    }
