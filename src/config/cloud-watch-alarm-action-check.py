import boto3

TAG_KEY = 'ConfigRule'
TAG_VALUE = 'True'

def get_tagged_instance_ids():
    resource_client = boto3.client('resourcegroupstaggingapi')
    instance_ids = []

    paginator = resource_client.get_paginator('get_resources')
    for page in paginator.paginate(
        TagFilters=[{'Key': TAG_KEY, 'Values': [TAG_VALUE]}],
        ResourceTypeFilters=['ec2:instance']
    ):
        for resource in page['ResourceTagMappingList']:
            arn = resource['ResourceARN']
            instance_id = arn.split('/')[-1]
            instance_ids.append(instance_id)

    return instance_ids

def get_alarms_for_instances(instance_ids):
    cloudwatch = boto3.client('cloudwatch')
    paginator = cloudwatch.get_paginator('describe_alarms')
    matching_alarms = []

    for page in paginator.paginate():
        for alarm in page['MetricAlarms']:
            for dim in alarm.get('Dimensions', []):
                if dim['Name'] == 'InstanceId' and dim['Value'] in instance_ids:
                    matching_alarms.append(alarm['AlarmName'])
                    break

    return list(set(matching_alarms))

def lambda_handler(event, context):
    print(f"🔍 Looking for EC2 instances with tag {TAG_KEY}={TAG_VALUE}")
    instance_ids = get_tagged_instance_ids()

    if not instance_ids:
        print("❌ No tagged EC2 instances found.")
        return {
            "status": "no_instances",
            "alarms": []
        }

    print(f"✅ Tagged EC2 Instance IDs: {instance_ids}")

    alarms = get_alarms_for_instances(instance_ids)

    if alarms:
        print("📢 Alarms matching tagged EC2 instances:")
        for name in alarms:
            print(f"- {name}")
    else:
        print("⚠️ No alarms found for these instances.")

    return {
        "status": "completed",
        "alarms": alarms
    }
