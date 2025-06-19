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

    try:
        alarms_response = cloudwatch.describe_alarms()
        all_alarms = alarms_response.get('MetricAlarms', [])
    except Exception as e:
        print(f"Error fetching alarms: {e}")
        all_alarms = []

    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instance_id = instance['InstanceId']
            timestamp = instance['LaunchTime']
            platform = instance.get('PlatformDetails', '')

            if platform != 'Linux/UNIX':
                continue

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

            path_status = {
                path: {'metric_found': False, 'alarm_found': False} for path in required_paths
            }

            try:
                paginator = cloudwatch.get_paginator('list_metrics')
                for page in paginator.paginate(
                    Namespace='HCOPS/ADF',
                    MetricName='disk_used_percent',
                    Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}]
                ):
                    for metric in page['Metrics']:
                        dims = {d['Name']: d['Value'] for d in metric.get('Dimensions', [])}
                        path = dims.get('path')
                        if path in path_status:
                            path_status[path]['metric_found'] = True
                            print(f"Metric found for {instance_id} at path: {path}")

                            # Alarm match logic with normalization
                            normalized_path = path.strip().lower()
                            normalized_instance_id = instance_id.strip().lower()

                            for alarm in all_alarms:
                                raw_alarm_name = alarm.get('AlarmName', '')
                                alarm_name_normalized = raw_alarm_name.replace('MountPoint :', 'MountPoint:').lower()

                                if (normalized_instance_id in alarm_name_normalized and 
                                    f"mountpoint:{normalized_path}" in alarm_name_normalized):
                                    path_status[path]['alarm_found'] = True
                                    print(f"Matched: Alarm '{raw_alarm_name}' contains instance ID and path '{path}'")
                                    break

                            if not path_status[path]['alarm_found']:
                                print(f"Not Matched: No alarm found for instance ID '{instance_id}' and path '{path}'")
            except Exception as e:
                print(f"Error listing metrics for {instance_id}: {e}")
                continue

            missing_metric_paths = [p for p, val in path_status.items() if not val['metric_found']]
            missing_alarm_paths = [p for p, val in path_status.items() if val['metric_found'] and not val['alarm_found']]

            if missing_metric_paths:
                compliance_type = 'NON_COMPLIANT'
                annotation = f"{os_flavor}: Missing disk_used_percent metrics for: {', '.join(missing_metric_paths)}"
            elif missing_alarm_paths:
                compliance_type = 'NON_COMPLIANT'
                annotation = f"{os_flavor}: Alarms missing for: {', '.join(missing_alarm_paths)}"
            else:
                compliance_type = 'COMPLIANT'
                annotation = f"{os_flavor}: All required disk_used_percent metrics and alarms are present."

            print(f"Evaluation: {instance_id} - {compliance_type}")
            print(f"Annotation: {annotation}")

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
            print("Submitted evaluations to AWS Config")
        except Exception as e:
            print(f"Error submitting evaluations: {e}")

    return {
        'status': 'completed',
        'evaluated': len(evaluations)
    }
