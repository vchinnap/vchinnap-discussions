import boto3
import botocore

# Retry-safe configuration
boto_config = botocore.config.Config(
    retries={
        'max_attempts': 5,
        'mode': 'standard'
    }
)

ec2 = boto3.client('ec2', config=boto_config)
cloudwatch = boto3.client('cloudwatch', config=boto_config)
config = boto3.client('config', config=boto_config)

def get_config_rule_instance_ids():
    instance_ids = []
    try:
        response = ec2.describe_instances(
            Filters=[{'Name': 'tag:ConfigRule', 'Values': ['True']}]
        )
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                instance_ids.append(instance['InstanceId'])
    except Exception as e:
        print(f"❌ Error fetching EC2 instances: {e}")
    return instance_ids

def lambda_handler(event, context):
    result_token = event.get('resultToken', 'TESTMODE')
    instance_ids = get_config_rule_instance_ids()

    if not instance_ids:
        print("ℹ️ No instances found with tag ConfigRule=True.")
        return {"message": "No matching EC2 instances."}

    evaluations = []

    try:
        paginator = cloudwatch.get_paginator('describe_alarms')
        for page in paginator.paginate(AlarmTypes=['MetricAlarm']):
            for alarm in page['MetricAlarms']:
                alarm_name = alarm['AlarmName']

                # Only include alarms that match EC2-tagged instances
                if not any(alarm_name.startswith(instance_id) for instance_id in instance_ids):
                    continue

                # Evaluate alarm actions
                has_alarm = bool(alarm.get('AlarmActions'))
                has_ok = bool(alarm.get('OKActions'))
                has_insufficient = bool(alarm.get('InsufficientDataActions'))

                if has_alarm and has_ok and has_insufficient:
                    compliance_type = 'COMPLIANT'
                    annotation = "✅ All required alarm actions are configured."
                else:
                    compliance_type = 'NON_COMPLIANT'
                    missing = []
                    if not has_alarm: missing.append("ALARM")
                    if not has_ok: missing.append("OK")
                    if not has_insufficient: missing.append("INSUFFICIENT_DATA")
                    annotation = f"⚠️ Missing actions for: {', '.join(missing)}"

                evaluations.append({
                    'ComplianceResourceType': 'AWS::CloudWatch::Alarm',
                    'ComplianceResourceId': alarm_name,
                    'ComplianceType': compliance_type,
                    'Annotation': annotation,
                    'OrderingTimestamp': alarm['AlarmConfigurationUpdatedTimestamp']
                })

    except Exception as e:
        print(f"❌ Error during alarm evaluation: {e}")
        return {"error": str(e)}

    # Submit to AWS Config
    if result_token != 'TESTMODE' and evaluations:
        try:
            config.put_evaluations(
                Evaluations=evaluations,
                ResultToken=result_token
            )
            print("✅ Evaluation results submitted to AWS Config.")
        except Exception as e:
            print(f"❌ Failed to submit evaluations to AWS Config: {e}")

    return {
        "status": "completed",
        "evaluated_alarms": len(evaluations)
    }
