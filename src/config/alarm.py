import boto3

cloudwatch = boto3.client('cloudwatch')

def get_alarms_for_instance(instance_id):
    matching_alarms = []

    paginator = cloudwatch.get_paginator('describe_alarms')
    for page in paginator.paginate(AlarmTypes=['MetricAlarm']):
        for alarm in page['MetricAlarms']:
            alarm_name = alarm['AlarmName']
            if alarm_name.startswith(instance_id):
                matching_alarms.append(alarm_name)

    return matching_alarms

# Example usage
instance_id = 'i-1234567890abcdef0'  # Replace with your actual instance ID
alarms = get_alarms_for_instance(instance_id)

print(f"🔍 Alarms for instance {instance_id}:")
for alarm in alarms:
    print(f" - {alarm}")
