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

# Expected metric coverage
ALLOWED_METRICS = [
    'disk_used_percent',
    'mem_used_percent',
    'CPUUtilization',
    'StatusCheckFailed',
    'Memory Available Bytes',
    'LogicalDisk % Free Space',
    'DISK_FREE'
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

            metric_instance_map[instance_id][metric_name] += 1
            total_alarms_matched += 1

            print(f"Matched alarm '{alarm_name}' for instance {instance_id} with metric '{metric_name}'")

            # ➤ Print and evaluate ActionsEnabled
            actions_enabled = alarm.get('ActionsEnabled', True)
            print(f"    ➤ ActionsEnabled: {actions_enabled}")

            if actions_enabled:
                compliance_type = 'COMPLIANT'
                annotation = f"Metric '{metric_name}' has alarm actions enabled (ActionsEnabled=True)."
            else:
                compliance_type = 'NON_COMPLIANT'
                annotation = f"Metric '{metric_name}' has alarm actions disabled (ActionsEnabled=False)."

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

    print("\n=== Alarm Coverage per Instance and Metric ===")
    for instance_id in instance_ids:
        print(f"\nInstance: {instance_id}")
        found_metrics = metric_instance_map[instance_id]
        for metric in ALLOWED_METRICS:
            count = found_metrics.get(metric, 0)
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
