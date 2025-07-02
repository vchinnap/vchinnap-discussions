import boto3
import botocore

# Retry-safe config
boto_config = botocore.config.Config(
    retries={'max_attempts': 5, 'mode': 'standard'}
)

ec2 = boto3.client('ec2', config=boto_config)
cloudwatch = boto3.client('cloudwatch', config=boto_config)
config = boto3.client('config', config=boto_config)

MAX_CONFIG_BATCH_SIZE = 100

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

def chunk_evaluations(evaluations, chunk_size=100):
    for i in range(0, len(evaluations), chunk_size):
        yield evaluations[i:i + chunk_size]

def lambda_handler(event, context):
    result_token = event.get('resultToken', 'TESTMODE')
    instance_ids = get_config_rule_instance_ids()

    if not instance_ids:
        print("ℹ️ No instances found with tag ConfigRule=True.")
        return {"message": "No matching EC2 instances."}

    evaluations = []
    total_alarms_matched = 0

    try:
        # Fetch all alarms
        paginator = cloudwatch.get_paginator('describe_alarms')
        all_alarms = []
        for page in paginator.paginate(AlarmTypes=['MetricAlarm']):
            all_alarms.extend(page['MetricAlarms'])

        print(f"🔍 Total alarms fetched from CloudWatch: {len(all_alarms)}")

        for instance_id in instance_ids:
            matching_alarms = [
                alarm for alarm in all_alarms
                if any(
                    d.get('Name') == 'InstanceId' and d.get('Value') == instance_id
                    for d in alarm.get('Dimensions', [])
                )
            ]

            print(f"📦 Instance {instance_id} has {len(matching_alarms)} alarms")

            total_alarms_matched += len(matching_alarms)

            for alarm in matching_alarms:
                alarm_name = alarm['AlarmName']
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

    # Submit in chunks
    if result_token != 'TESTMODE' and evaluations:
        for chunk in chunk_evaluations(evaluations, MAX_CONFIG_BATCH_SIZE):
            try:
                config.put_evaluations(
                    Evaluations=chunk,
                    ResultToken=result_token
                )
            except Exception as e:
                print(f"❌ Failed to submit evaluation chunk: {e}")

        print(f"✅ Submitted {len(evaluations)} evaluations to AWS Config.")

    return {
        "status": "completed",
        "instances_evaluated": len(instance_ids),
        "alarms_evaluated": total_alarms_matched
    }






'''
import boto3

ec2 = boto3.client('ec2')
cloudwatch = boto3.client('cloudwatch')

def get_config_rule_instances():
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

def get_alarms_for_instance(instance_id):
    matching_alarms = []
    try:
        paginator = cloudwatch.get_paginator('describe_alarms')
        for page in paginator.paginate(AlarmTypes=['MetricAlarm']):
            for alarm in page['MetricAlarms']:
                alarm_name = alarm['AlarmName']
                if alarm_name.startswith(instance_id):
                    matching_alarms.append(alarm_name)
    except Exception as e:
        print(f"❌ Error fetching alarms for {instance_id}: {e}")
    return matching_alarms

def lambda_handler(event, context):
    instance_ids = get_config_rule_instances()

    result = {}

    if not instance_ids:
        print("ℹ️ No instances found with tag ConfigRule=True")
        return {"message": "No instances found with tag ConfigRule=True"}

    for instance_id in instance_ids:
        alarms = get_alarms_for_instance(instance_id)
        print(f"\n🔍 Alarms for instance {instance_id}:")
        if alarms:
            for alarm in alarms:
                print(f" - {alarm}")
        else:
            print(" ⚠️ No matching alarms found.")
        result[instance_id] = alarms

    return {
        "status": "completed",
        "alarm_summary": result
    }

    '''


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

MAX_CONFIG_BATCH_SIZE = 100

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

def chunk_evaluations(evaluations, chunk_size=100):
    for i in range(0, len(evaluations), chunk_size):
        yield evaluations[i:i + chunk_size]

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

                # Filter: Only process alarms tied to tagged EC2s
                if not any(alarm_name.startswith(instance_id) for instance_id in instance_ids):
                    continue

                # Action checks
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

    # Submit evaluations in chunks
    if result_token != 'TESTMODE' and evaluations:
        for chunk in chunk_evaluations(evaluations, MAX_CONFIG_BATCH_SIZE):
            try:
                config.put_evaluations(
                    Evaluations=chunk,
                    ResultToken=result_token
                )
            except Exception as e:
                print(f"❌ Failed to submit evaluation chunk: {e}")

        print(f"✅ Submitted {len(evaluations)} evaluations to AWS Config.")

    return {
        "status": "completed",
        "evaluated_alarms": len(evaluations)
    }
