import boto3
from datetime import datetime, timezone

config = boto3.client('config')
ec2 = boto3.client('ec2')
cloudwatch = boto3.client('cloudwatch')

def lambda_handler(event, context):
    result_token = event.get('resultToken', 'TESTMODE')
    evaluations = []

    # Get EC2s with tag ConfigRule=True
    try:
        response = ec2.describe_instances(
            Filters=[{'Name': 'tag:ConfigRule', 'Values': ['True']}]
        )
    except Exception as e:
        print(f"Error fetching EC2 instances: {e}")
        return

    # Fetch all CloudWatch alarms once
    try:
        alarms_response = cloudwatch.describe_alarms()
        alarm_names = [alarm['AlarmName'] for alarm in alarms_response.get('MetricAlarms', [])]
    except Exception as e:
        print(f"Error fetching alarms: {e}")
        alarm_names = []

    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instance_id = instance['InstanceId']
            timestamp = instance['LaunchTime']
            platform = instance.get('PlatformDetails', '')

            # Filter only Linux/UNIX
            if platform != 'Linux/UNIX':
                continue

            # Determine OS flavor from AMI name
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

            path_metrics = {path: False for path in required_paths}

            # Check CloudWatch metrics for disk_used_percent
            try:
                paginator = cloudwatch.get_paginator('list_metrics')
                for page in paginator.paginate(
                    Namespace='HCOPS/ADF',
                    MetricName='disk_used_percent',
                    Dimensions=[
                        {'Name': 'InstanceId', 'Value': instance_id}
                    ]
                ):
                    for metric in page['Metrics']:
                        dims = {d['Name']: d['Value'] for d in metric.get('Dimensions', [])}
                        path = dims.get('path')
                        if path in path_metrics:
                            path_metrics[path] = True
                            print(f"Metric found for {instance_id} at path: {path}")

                            # Check if any alarm contains both instance ID and exact path
                            matched = False
                            for alarm_name in alarm_names:
                                if instance_id in alarm_name and path in alarm_name:
                                    print(f"Matched: Alarm '{alarm_name}' contains instance ID and path '{path}'")
                                    matched = True
                                    break

                            if not matched:
                                print(f"Not Matched: No alarm found for instance ID '{instance_id}' and path '{path}'")

            except Exception as e:
                print(f"Error listing metrics for {instance_id}: {e}")
                continue

            # Evaluate compliance
            missing_paths = [path for path, found in path_metrics.items() if not found]
            if not missing_paths:
                compliance_type = 'COMPLIANT'
                annotation = f"{os_flavor}: All required disk_used_percent metrics are present."
            else:
                compliance_type = 'NON_COMPLIANT'
                annotation = f"{os_flavor}: Missing disk_used_percent metrics for: {', '.join(missing_paths)}"

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
