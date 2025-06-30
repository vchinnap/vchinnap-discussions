'''
import boto3
from datetime import datetime, timezone

TAG_KEY = 'ConfigRule'
TAG_VALUE = 'Rule'

cloudwatch = boto3.client('cloudwatch')
config = boto3.client('config')

def get_alarms_with_specific_tag_and_actions():
    matching_alarms = []

    paginator = cloudwatch.get_paginator('describe_alarms')
    for page in paginator.paginate():
        for alarm in page['MetricAlarms']:
            alarm_arn = alarm['AlarmArn']
            alarm_name = alarm['AlarmName']

            try:
                tags_response = cloudwatch.list_tags_for_resource(ResourceARN=alarm_arn)
                tags = {tag['Key']: tag['Value'] for tag in tags_response.get('Tags', [])}
                if tags.get(TAG_KEY) == TAG_VALUE:
                    has_alarm = bool(alarm.get('AlarmActions'))
                    has_ok = bool(alarm.get('OKActions'))
                    has_insufficient = bool(alarm.get('InsufficientDataActions'))

                    compliant = has_alarm and has_ok and has_insufficient
                    annotation_parts = []
                    if not has_alarm:
                        annotation_parts.append("Missing AlarmActions")
                    if not has_ok:
                        annotation_parts.append("Missing OKActions")
                    if not has_insufficient:
                        annotation_parts.append("Missing InsufficientDataActions")
                    annotation = " | ".join(annotation_parts) if annotation_parts else "All required actions are present."

                    matching_alarms.append({
                        'AlarmName': alarm_name,
                        'AlarmArn': alarm_arn,
                        'ComplianceType': 'COMPLIANT' if compliant else 'NON_COMPLIANT',
                        'Annotation': annotation,
                        'OrderingTimestamp': datetime.now(timezone.utc)
                    })
            except Exception as e:
                print(f"⚠️ Could not fetch tags for alarm {alarm_name}: {e}")

    return matching_alarms

def lambda_handler(event, context):
    print(f"🔍 Looking for CloudWatch alarms tagged {TAG_KEY}={TAG_VALUE}")
    result_token = event.get('resultToken', 'TESTMODE')
    alarms = get_alarms_with_specific_tag_and_actions()
    evaluations = []

    for alarm in alarms:
        evaluations.append({
            'ComplianceResourceType': 'AWS::CloudWatch::Alarm',
            'ComplianceResourceId': alarm['AlarmName'],
            'ComplianceType': alarm['ComplianceType'],
            'Annotation': alarm['Annotation'],
            'OrderingTimestamp': alarm['OrderingTimestamp']
        })

        print(f"📝 {alarm['AlarmName']}: {alarm['ComplianceType']} → {alarm['Annotation']}")

    # ✅ Submit evaluations to AWS Config (only in real evaluation mode)
    if result_token != 'TESTMODE' and evaluations:
        try:
            config.put_evaluations(
                Evaluations=evaluations,
                ResultToken=result_token
            )
            print("✅ Submitted evaluations to AWS Config")
        except Exception as e:
            print(f"❌ Error submitting evaluations to AWS Config: {e}")
    else:
        print("🧪 Skipped AWS Config evaluation submission (TESTMODE or no evaluations)")

    return {
        "status": "completed",
        "evaluated_count": len(evaluations)
    }

'''
import boto3
from datetime import datetime, timezone

TAG_KEY = 'ConfigRule'
TAG_VALUE = 'True'

cloudwatch = boto3.client('cloudwatch')
config = boto3.client('config')

def get_alarms_with_specific_tag_and_actions():
    matching_alarms = []

    paginator = cloudwatch.get_paginator('describe_alarms')
    for page in paginator.paginate():
        for alarm in page['MetricAlarms']:
            alarm_arn = alarm['AlarmArn']
            alarm_name = alarm['AlarmName']

            try:
                tags_response = cloudwatch.list_tags_for_resource(ResourceARN=alarm_arn)
                tags = {tag['Key']: tag['Value'] for tag in tags_response.get('Tags', [])}
                if tags.get(TAG_KEY) == TAG_VALUE:
                    has_alarm = bool(alarm.get('AlarmActions'))
                    has_ok = bool(alarm.get('OKActions'))
                    has_insufficient = bool(alarm.get('InsufficientDataActions'))

                    compliant = has_alarm and has_ok and has_insufficient
                    annotation_parts = []
                    if not has_alarm:
                        annotation_parts.append("Missing AlarmActions")
                    if not has_ok:
                        annotation_parts.append("Missing OKActions")
                    if not has_insufficient:
                        annotation_parts.append("Missing InsufficientDataActions")
                    annotation = " | ".join(annotation_parts) if annotation_parts else "All required actions are present."

                    matching_alarms.append({
                        'AlarmName': alarm_name,
                        'AlarmArn': alarm_arn,
                        'ComplianceType': 'COMPLIANT' if compliant else 'NON_COMPLIANT',
                        'Annotation': annotation,
                        'Timestamp': datetime.now(timezone.utc).isoformat()  # ✅ ISO format for JSON safety
                    })
            except Exception as e:
                print(f"⚠️ Could not fetch tags for alarm {alarm_name}: {e}")

    return matching_alarms

def lambda_handler(event, context):
    print(f"🔍 Looking for CloudWatch alarms tagged {TAG_KEY}={TAG_VALUE}")
    result_token = event.get('resultToken', 'TESTMODE')  # Ignore for SSM test
    alarms = get_alarms_with_specific_tag_and_actions()
    evaluations = []

    for alarm in alarms:
        evaluations.append({
            'ComplianceResourceType': 'AWS::CloudWatch::Alarm',
            'ComplianceResourceId': alarm['AlarmName'],
            'ComplianceType': alarm['ComplianceType'],
            'Annotation': alarm['Annotation'],
            'OrderingTimestamp': alarm['Timestamp']  # Already ISO formatted
        })

        print(f"📝 {alarm['AlarmName']}: {alarm['ComplianceType']} → {alarm['Annotation']}")

    # ✅ Commented for SSM testing (safe)
    # if result_token != 'TESTMODE' and evaluations:
    #     try:
    #         config.put_evaluations(
    #             Evaluations=[
    #                 {
    #                     **e,
    #                     'OrderingTimestamp': datetime.fromisoformat(e['OrderingTimestamp'])  # Convert back if needed
    #                 } for e in evaluations
    #             ],
    #             ResultToken=result_token
    #         )
    #         print("✅ Submitted evaluations to AWS Config")
    #     except Exception as e:
    #         print(f"❌ Error submitting evaluations to AWS Config: {e}")

    print("🧪 Test mode: Skipped AWS Config evaluation submission")

    return {
        "status": "completed",
        "evaluated_count": len(evaluations),
        "evaluations": evaluations
    }
