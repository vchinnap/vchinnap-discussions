import boto3
import json
from datetime import datetime

ec2 = boto3.client('ec2')
cloudwatch = boto3.client('cloudwatch')
config = boto3.client('config')

TAG_KEY = 'ConfigRule'
TAG_VALUE = 'True'

def lambda_handler(event, context):
    result_token = event.get('resultToken', 'TESTMODE')
    evaluations = []

    try:
        instances = ec2.describe_instances(
            Filters=[{'Name': f'tag:{TAG_KEY}', 'Values': [TAG_VALUE]}]
        )
    except Exception as e:
        print(f"❌ Error fetching EC2 instances: {e}")
        return

    instance_ids = []
    instance_platforms = {}

    for reservation in instances['Reservations']:
        for instance in reservation['Instances']:
            instance_id = instance['InstanceId']
            platform = instance.get('PlatformDetails', 'Unknown')
            timestamp = instance['LaunchTime']
            instance_ids.append(instance_id)
            instance_platforms[instance_id] = {
                'platform': platform,
                'timestamp': timestamp
            }

    if not instance_ids:
        print("ℹ️ No EC2 instances found with tag ConfigRule=True.")
        return

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
        print(f"\n🔍 Evaluating alarms for Instance ID: {instance_id}")
        platform = instance_platforms[instance_id]['platform']
        timestamp = instance_platforms[instance_id]['timestamp']
        
        alarms_for_instance = [
            alarm for alarm in all_alarms
            if any(
                dim['Name'] == 'InstanceId' and dim['Value'] == instance_id
                for dim in alarm.get('Dimensions', [])
            )
        ]

        if not alarms_for_instance:
            annotation = f"{platform}: No CloudWatch alarms found for this instance."
            compliance_type = 'NON_COMPLIANT'
        else:
            missing_action_alarms = []
            for alarm in alarms_for_instance:
                has_alarm = bool(alarm.get('AlarmActions'))
                has_ok = bool(alarm.get('OKActions'))
                has_insufficient = bool(alarm.get('InsufficientDataActions'))

                if not (has_alarm and has_ok and has_insufficient):
                    missing_action_alarms.append(alarm['AlarmName'])

            if missing_action_alarms:
                compliance_type = 'NON_COMPLIANT'
                annotation = f"{platform}: Alarms without full action config: {', '.join(missing_action_alarms)}"
            else:
                compliance_type = 'COMPLIANT'
                annotation = f"{platform}: All alarms have ALARM, OK, and INSUFFICIENT_DATA actions configured."

        print(f"📌 {instance_id} → {compliance_type}")
        print(f"📝 {annotation}")

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
            print(f"❌ Error submitting evaluations: {e}")

    return {
        'status': 'completed',
        'evaluated': len(evaluations)
    }
