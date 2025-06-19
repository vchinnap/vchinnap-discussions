import boto3
import json
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
            elif 'amzn' in ami_name or 'al2' in ami_name:
                os_flavor = 'Amazon Linux'
            else:
                print(f"Skipping unsupported AMI: {ami_name}")
                continue

            # Check if any alarm exists for this instance and metric
            alarm_found = False
            print(f"\n🔍 Checking alarms for instance: {instance_id}")

            for alarm in all_alarms:
                if alarm.get('MetricName') != 'disk_used_percent':
                    continue

                dims = {d['Name']: d['Value'] for d in alarm.get('Dimensions', [])}
                if dims.get('InstanceId') == instance_id:
                    alarm_found = True
                    print(f"✅ Found alarm for instance {instance_id}: {alarm.get('AlarmName')}")
                    print(json.dumps(alarm, indent=2, default=str))
                    break

            if alarm_found:
                compliance_type = 'COMPLIANT'
                annotation = f"{os_flavor}: At least one disk_used_percent alarm exists for this instance."
            else:
                compliance_type = 'NON_COMPLIANT'
                annotation = f"{os_flavor}: No disk_used_percent alarm found for this instance."

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
            print("✅ Submitted evaluations to AWS Config")
        except Exception as e:
            print(f"Error submitting evaluations: {e}")

    return {
        'status': 'completed',
        'evaluated': len(evaluations)
    }
