'''
import boto3

TAG_KEY = 'ConfigRule'
TAG_VALUE = 'Rule'

def get_alarms_with_specific_tag():
    cloudwatch = boto3.client('cloudwatch')
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
                    matching_alarms.append(alarm_name)
            except Exception as e:
                print(f"⚠️ Could not fetch tags for alarm {alarm_name}: {e}")

    return matching_alarms

def lambda_handler(event, context):
    print(f"🔍 Looking for CloudWatch alarms tagged {TAG_KEY}={TAG_VALUE}")
    alarms = get_alarms_with_specific_tag()

    if alarms:
        print("📢 Alarms with the specified tag:")
        for name in alarms:
            print(f"- {name}")
    else:
        print("⚠️ No alarms found with the specified tag.")

    return {
        "status": "completed",
        "alarms": alarms
    }
'''


import boto3

TAG_KEY = 'ConfigRule'
TAG_VALUE = 'Rule'

def get_alarms_with_specific_tag_and_actions():
    cloudwatch = boto3.client('cloudwatch')
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
                    alarm_info = {
                        'AlarmName': alarm_name,
                        'AlarmArn': alarm_arn,
                        'AlarmActionRequired': bool(alarm.get('AlarmActions')),
                        'OKActionRequired': bool(alarm.get('OKActions')),
                        'InsufficientDataActionRequired': bool(alarm.get('InsufficientDataActions'))
                    }
                    matching_alarms.append(alarm_info)
            except Exception as e:
                print(f"⚠️ Could not fetch tags for alarm {alarm_name}: {e}")

    return matching_alarms

def lambda_handler(event, context):
    print(f"🔍 Looking for CloudWatch alarms tagged {TAG_KEY}={TAG_VALUE}")
    alarms = get_alarms_with_specific_tag_and_actions()

    if alarms:
        print("📢 Alarms with tag and action checks:")
        for alarm in alarms:
            print(f"- {alarm['AlarmName']}")
            print(f"  🔔 AlarmActionsPresent: {alarm['AlarmActionRequired']}")
            print(f"  ✅ OKActionsPresent: {alarm['OKActionRequired']}")
            print(f"  ❓ InsufficientDataActionsPresent: {alarm['InsufficientDataActionRequired']}")
    else:
        print("⚠️ No alarms found with the specified tag.")

    return {
        "status": "completed",
        "alarms": alarms
    }
