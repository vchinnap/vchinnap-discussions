import boto3
from datetime import datetime, timezone

config = boto3.client('config')
ec2 = boto3.client('ec2')
cloudwatch = boto3.client('cloudwatch')

def lambda_handler(event, context):
    result_token = event.get('resultToken', 'TESTMODE')
    evaluations = []

    # Get all EC2s with ConfigRule=True tag
    response = ec2.describe_instances(
        Filters=[
            {'Name': 'tag:ConfigRule', 'Values': ['True']}
        ]
    )

    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instance_id = instance['InstanceId']
            timestamp = instance['LaunchTime']

            # Default state: assume non-compliant
            compliance_type = 'NON_COMPLIANT'
            annotation = "Missing CPUUtilization alarm"

            # Check for CPUUtilization alarm
            alarms = cloudwatch.describe_alarms(AlarmTypes=['MetricAlarm'])['MetricAlarms']
            for alarm in alarms:
                dimensions = {d['Name']: d['Value'] for d in alarm.get('Dimensions', [])}
                if dimensions.get('InstanceId') == instance_id and alarm.get('MetricName') == 'CPUUtilization':
                    compliance_type = 'COMPLIANT'
                    annotation = "CPUUtilization alarm is present"
                    break

            # Append result
            evaluations.append({
                'ComplianceResourceType': 'AWS::EC2::Instance',
                'ComplianceResourceId': instance_id,
                'ComplianceType': compliance_type,
                'Annotation': annotation,
                'OrderingTimestamp': timestamp
            })

    # Submit to AWS Config
    if result_token != 'TESTMODE' and evaluations:
        config.put_evaluations(
            Evaluations=evaluations,
            ResultToken=result_token
        )

    return {
        'status': 'completed',
        'evaluated': len(evaluations)
    }








=============


import boto3
import json
from datetime import datetime, timezone

cloudwatch = boto3.client('cloudwatch')
config = boto3.client('config')

TAG_KEY = 'ConfigRule'
TAG_VALUE = 'Rule'

def evaluate_alarm_compliance(alarm_name, alarm_arn):
    try:
        tags_response = cloudwatch.list_tags_for_resource(ResourceARN=alarm_arn)
        tags = {tag['Key']: tag['Value'] for tag in tags_response.get('Tags', [])}

        if tags.get(TAG_KEY) != TAG_VALUE:
            return None  # Skip alarms that don't have the correct tag

        alarm_details = cloudwatch.describe_alarms(AlarmNames=[alarm_name])['MetricAlarms'][0]

        has_alarm = bool(alarm_details.get('AlarmActions'))
        has_ok = bool(alarm_details.get('OKActions'))
        has_insufficient = bool(alarm_details.get('InsufficientDataActions'))

        compliant = has_alarm and has_ok and has_insufficient

        annotation_parts = []
        if not has_alarm:
            annotation_parts.append("Missing AlarmActions")
        if not has_ok:
            annotation_parts.append("Missing OKActions")
        if not has_insufficient:
            annotation_parts.append("Missing InsufficientDataActions")

        annotation = " | ".join(annotation_parts) if annotation_parts else "All required actions are present."

        return {
            'ComplianceResourceType': 'AWS::CloudWatch::Alarm',
            'ComplianceResourceId': alarm_name,
            'ComplianceType': 'COMPLIANT' if compliant else 'NON_COMPLIANT',
            'Annotation': annotation,
            'OrderingTimestamp': datetime.now(timezone.utc)
        }

    except Exception as e:
        print(f"❌ Error evaluating alarm {alarm_name}: {e}")
        return None

def lambda_handler(event, context):
    print("🔍 AWS Config change-triggered evaluation started.")
    print("Event:", json.dumps(event))

    result_token = event.get('resultToken', 'TESTMODE')
    invoking_event = json.loads(event.get('invokingEvent', '{}'))

    config_item = invoking_event.get('configurationItem', {})
    resource_type = config_item.get('resourceType')
    resource_id = config_item.get('resourceId')

    if resource_type != "AWS::CloudWatch::Alarm":
        print(f"❌ Skipping non-alarm resource: {resource_type}")
        return {"status": "skipped", "reason": "Not a CloudWatch alarm"}

    print(f"🔔 Evaluating alarm: {resource_id}")

    alarm_arn = config_item.get('ARN')
    evaluation = evaluate_alarm_compliance(resource_id, alarm_arn)

    if evaluation:
        if result_token != 'TESTMODE':
            try:
                config.put_evaluations(
                    Evaluations=[evaluation],
                    ResultToken=result_token
                )
                print(f"✅ Submitted evaluation for {resource_id}")
            except Exception as e:
                print(f"❌ Failed to submit evaluation: {e}")
    else:
        print("⚠️ No evaluation generated (tag mismatch or error)")

    return {
        "status": "completed",
        "evaluated": 1 if evaluation else 0
    }
