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

            path_alarms = {path: False for path in required_paths}

            print(f"\nChecking alarms for instance: {instance_id}")
            for alarm in all_alarms:
                if alarm.get('MetricName') != 'disk_used_percent':
                    continue

                dims = {d['Name']: d['Value'] for d in alarm.get('Dimensions', [])}
                alarm_instance_id = dims.get('InstanceId')
                alarm_path = dims.get('path')

                if alarm_instance_id == instance_id and alarm_path in path_alarms:
                    path_alarms[alarm_path] = True
                    print(f"Matched alarm for instance {instance_id}, path {alarm_path}: {alarm.get('AlarmName')}")

            missing_paths = [p for p, found in path_alarms.items() if not found]

            if missing_paths:
                compliance_type = 'NON_COMPLIANT'
                annotation = f"{os_flavor}: Alarms missing for paths: {', '.join(missing_paths)}"
            else:
                compliance_type = 'COMPLIANT'
                annotation = f"{os_flavor}: All required disk_used_percent alarms are present."

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
