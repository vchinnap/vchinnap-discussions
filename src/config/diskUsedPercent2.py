import boto3
from datetime import datetime, timezone

config = boto3.client('config')
ec2 = boto3.client('ec2')
cloudwatch = boto3.client('cloudwatch')

def lambda_handler(event, context):
    result_token = event.get('resultToken', 'TESTMODE')
    evaluations = []

    print("=== Starting EC2 compliance evaluation ===")

    try:
        print("Fetching EC2 instances with tag ConfigRule=True...")
        response = ec2.describe_instances(
            Filters=[{'Name': 'tag:ConfigRule', 'Values': ['True']}]
        )
        print(f"Total reservations fetched: {len(response['Reservations'])}")
    except Exception as e:
        print(f"ERROR: Failed to describe EC2 instances - {e}")
        return

    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instance_id = instance['InstanceId']
            timestamp = instance['LaunchTime']
            platform = instance.get('PlatformDetails', '')

            print(f"\n--- Processing instance: {instance_id} ---")
            print(f"PlatformDetails: {platform}")

            if platform != 'Linux/UNIX':
                print(f"Skipping: Not a Linux/UNIX instance.")
                continue

            # Step 1: Determine OS flavor
            image_id = instance['ImageId']
            try:
                image = ec2.describe_images(ImageIds=[image_id])['Images'][0]
                ami_name = image.get('Name', '').lower()
                print(f"AMI Name: {ami_name}")
            except Exception as e:
                print(f"ERROR: Failed to fetch AMI for instance {instance_id} - {e}")
                continue

            if 'rhel' in ami_name or 'redhat' in ami_name:
                os_flavor = 'Red Hat Linux'
                required_paths = ['/var', '/tmp', '/var/log', '/var/log/audit', '/home', '/opt', '/usr']
            elif 'amzn' in ami_name or 'al2' in ami_name:
                os_flavor = 'Amazon Linux'
                required_paths = ['/']
            else:
                print(f"Unsupported OS detected from AMI. Skipping instance.")
                continue

            print(f"OS Flavor: {os_flavor}")
            print(f"Required paths to validate: {required_paths}")

            # Step 2: Discover metric paths
            found_paths = set()
            print("Fetching list of disk_used_percent metrics...")
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
                print(f"ERROR: Failed to list metrics - {e}")
                continue

            if not found_paths:
                print(f"No required metric paths found. Skipping instance.")
                continue

            # Step 3: Check alarms for each found path
            print("Checking CloudWatch alarms...")
            path_alarms = {path: False for path in found_paths}

            try:
                alarms = cloudwatch.describe_alarms(AlarmTypes=['MetricAlarm'])['MetricAlarms']
                print(f"Total alarms fetched: {len(alarms)}")
                for alarm in alarms:
                    if alarm.get('MetricName') != 'disk_used_percent':
                        continue

                    dims = {d['Name']: d['Value'] for d in alarm.get('Dimensions', [])}
                    if dims.get('InstanceId') != instance_id:
                        continue

                    for path in found_paths:
                        if dims.get('path') == path:
                            path_alarms[path] = True
                            print(f"Matched alarm: {alarm['AlarmName']} for path: {path}")
                            break
            except Exception as e:
                print(f"ERROR: Failed to describe alarms - {e}")
                continue

            # Step 4: Evaluate compliance
            print("Evaluating compliance status...")
            missing_paths = [path for path, has_alarm in path_alarms.items() if not has_alarm]

            if not missing_paths:
                compliance_type = 'COMPLIANT'
                annotation = f"{os_flavor}: Alarms exist for all required paths."
                print(f"Instance is COMPLIANT.")
            else:
                compliance_type = 'NON_COMPLIANT'
                annotation = f"{os_flavor}: Missing alarms for paths: {', '.join(missing_paths)}"
                print(f"Instance is NON_COMPLIANT. Missing alarms for: {missing_paths}")

            evaluations.append({
                'ComplianceResourceType': 'AWS::EC2::Instance',
                'ComplianceResourceId': instance_id,
                'ComplianceType': compliance_type,
                'Annotation': annotation,
                'OrderingTimestamp': timestamp
            })

    # Step 5: Submit to AWS Config
    print(f"\nSubmitting {len(evaluations)} evaluations to AWS Config...")
    if result_token != 'TESTMODE' and evaluations:
        try:
            config.put_evaluations(Evaluations=evaluations, ResultToken=result_token)
            print("Evaluations successfully submitted.")
        except Exception as e:
            print(f"ERROR: Failed to submit evaluations - {e}")

    print("=== Evaluation complete ===")
    return {
        'status': 'completed',
        'evaluated': len(evaluations)
    }
