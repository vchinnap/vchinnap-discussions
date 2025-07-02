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

# Execute the logic directly
instance_ids = get_config_rule_instances()

if not instance_ids:
    print("ℹ️ No instances found with tag ConfigRule=True")

for instance_id in instance_ids:
    alarms = get_alarms_for_instance(instance_id)
    print(f"\n🔍 Alarms for instance {instance_id}:")
    if alarms:
        for alarm in alarms:
            print(f" - {alarm}")
    else:
        print(" ⚠️ No matching alarms found.")
