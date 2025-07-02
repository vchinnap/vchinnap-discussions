import boto3
import botocore
from collections import defaultdict

boto_config = botocore.config.Config(
    retries={'max_attempts': 5, 'mode': 'standard'}
)

ec2 = boto3.client('ec2', config=boto_config)
cloudwatch = boto3.client('cloudwatch', config=boto_config)
config = boto3.client('config', config=boto_config)

MAX_CONFIG_BATCH_SIZE = 100

# Expected metric coverage (for validation)
ALLOWED_METRICS = [
    'disk_used_percent',
    'mem_used_percent',
    'CPUUtilization',
    'StatusCheckFailed',
    'Memory Available Bytes',
    'LogicalDisk % Free Space'
]

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
        print(f"Error fetching EC2 instances: {e}")
    return instance_ids

def chunk_evaluations(evaluations, chunk_size=100):
    for i in range(0, len(evaluations), chunk_size):
        yield evaluations[i:i + chunk_size]

def lambda_handler(event, context):
    result_token = event.get('resultToken', 'TESTMODE')
    instance_ids = get_config_rule_instance_ids()

    if not instance_ids:
        print("No instances found with tag ConfigRule=True.")
        return {"message": "No matching EC2 instances."}

    print("=== All EC2 Instances with tag ConfigRule=True ===")
    for instance_id in instance_ids:
        print(f"- {instance_id}")

    evaluations = []
    total_alarms_matched = 0
    total_alarms_skipped = 0

    # instance_id -> metric_name -> count
    metric_instance_map = defaultdict(lambda: defaultdict(int))

    try:
        paginator = cloudwatch.get_paginator('describe_alarms')
        all_alarms = []
        for page in paginator.paginate(AlarmTypes=['MetricAlarm']):
            all_alarms.extend(page['MetricAlarms'])

        print(f"Total alarms fetched from CloudWatch: {len(all_alarms)}")

        for alarm in all_alarms:
            alarm_name = alarm['AlarmName']
            metric_name = alarm.get('MetricName')
            dimensions = alarm.get('Dimensions', [])

            if metric_name not in ALLOWED_METRICS:
                total_alarms_skipped += 1
                continue

            instance_id = None
            for d in dimensions:
                if d.get('Name') == 'InstanceId':
                    instance_id = d.get('Value')
                    break

            if not instance_id or instance_id not in instance_ids:
                total_alarms_skipped += 1
                continue

            # Track metric presence per instance
            metric_instance_map[instance_id][metric_name] += 1
            total_alarms_matched += 1

            print(f"Matched alarm '{alarm_name}' for instance {instance_id} with metric '{metric_name}'")

            has_alarm = bool(alarm.get('AlarmActions'))
            has_ok = bool(alarm.get('OKActions'))
            has_insufficient = bool(alarm.get('InsufficientDataActions'))

            if has_alarm and has_ok and has_insufficient:
                compliance_type = 'COMPLIANT'
                annotation = "All required alarm actions are configured."
            else:
                compliance_type = 'NON_COMPLIANT'
                missing = []
                if not has_alarm: missing.append("ALARM")
                if not has_ok: missing.append("OK")
                if not has_insufficient: missing.append("INSUFFICIENT_DATA")
                annotation = f"Missing actions for: {', '.join(missing)}"

            evaluations.append({
                'ComplianceResourceType': 'AWS::CloudWatch::Alarm',
                'ComplianceResourceId': alarm_name,
                'ComplianceType': compliance_type,
                'Annotation': annotation,
                'OrderingTimestamp': alarm['AlarmConfigurationUpdatedTimestamp']
            })

    except Exception as e:
        print(f"Error during alarm evaluation: {e}")
        return {"error": str(e)}

    if result_token != 'TESTMODE' and evaluations:
        for chunk in chunk_evaluations(evaluations, MAX_CONFIG_BATCH_SIZE):
            try:
                config.put_evaluations(
                    Evaluations=chunk,
                    ResultToken=result_token
                )
            except Exception as e:
                print(f"Failed to submit evaluation chunk: {e}")

        print(f"Submitted {len(evaluations)} evaluations to AWS Config.")

    # Print alarm summary
    print("\n=== Alarm Coverage Report ===")
    for instance_id in instance_ids:
        print(f"\nInstance: {instance_id}")
        found_metrics = set(metric_instance_map[instance_id].keys())
        for metric in ALLOWED_METRICS:
            count = metric_instance_map[instance_id][metric]
            if count > 0:
                print(f"  ✅ {metric}: {count} alarms")
            else:
                print(f"  ❌ {metric}: 0 alarms (MISSING)")

    return {
        "status": "completed",
        "instances_evaluated": len(instance_ids),
        "alarms_matched": total_alarms_matched,
        "alarms_skipped": total_alarms_skipped,
        "evaluations_submitted": len(evaluations)
    }
