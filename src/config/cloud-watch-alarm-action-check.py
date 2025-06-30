import boto3
import time
from datetime import datetime, timezone
from botocore.exceptions import ClientError

config = boto3.client('config')
cloudwatch = boto3.client('cloudwatch')

def lambda_handler(event, context):
    result_token = event.get('resultToken', 'TESTMODE')
    evaluations = []

    try:
        response = cloudwatch.describe_alarms()
        alarms = response.get('MetricAlarms', [])

        for alarm in alarms:
            alarm_name = alarm['AlarmName']
            alarm_arn = alarm['AlarmArn']

            # ✅ Filter: Only alarms tagged with ConfigRule=True
            try:
                time.sleep(0.2)  # Slow down to avoid throttling
                tag_response = cloudwatch.list_tags_for_resource(ResourceARN=alarm_arn)
                tags = {tag['Key']: tag['Value'] for tag in tag_response.get('Tags', [])}
                if tags.get('ConfigRule') != 'True':
                    continue
            except ClientError as e:
                print(f"❌ Error fetching tags for {alarm_name}: {e}")
                continue

            # ✅ Check for missing action states
            compliant = True
            annotation = []

            if not alarm.get('AlarmActions'):
                compliant = False
                annotation.append('No AlarmActions')
            if not alarm.get('InsufficientDataActions'):
                compliant = False
                annotation.append('No InsufficientDataActions')
            if not alarm.get('OKActions'):
                compliant = False
                annotation.append('No OKActions')

            evaluations.append({
                'ComplianceResourceType': 'AWS::CloudWatch::Alarm',
                'ComplianceResourceId': alarm_name,
                'ComplianceType': 'COMPLIANT' if compliant else 'NON_COMPLIANT',
                'Annotation': ', '.join(annotation) or 'All actions present',
                'OrderingTimestamp': datetime.now(timezone.utc)
            })

    except Exception as e:
        print(f"❌ Error evaluating alarms: {e}")

    if result_token != 'TESTMODE' and evaluations:
        config.put_evaluations(
            Evaluations=evaluations,
            ResultToken=result_token
        )

    return {
        'status': 'completed',
        'evaluated': len(evaluations)
    }
