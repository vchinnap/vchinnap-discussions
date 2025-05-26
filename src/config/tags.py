import boto3
import os
import json

def lambda_handler(event, context):
    config = boto3.client('config')
    rule_arn = os.environ['CONFIG_RULE_ARN']

    tag_key_map = json.loads(os.environ.get('TAG_KEY_MAP', '{}'))
    tags = []

    for env_key, original_tag_key in tag_key_map.items():
        value = os.environ.get(env_key)
        if value:
            tags.append({'Key': original_tag_key, 'Value': value})

    print("🔖 Applying tags:", tags)

    if event['RequestType'] == 'Create':
        config.tag_resource(
            ResourceArn=rule_arn,
            Tags=tags
        )

    return {
        'PhysicalResourceId': f'{rule_arn}-TagApplied'
    }


















import boto3
import os

config = boto3.client('config')

def lambda_handler(event, context):
    arn = os.environ['CONFIG_RULE_ARN']
    if event['RequestType'] == 'Create':
        config.tag_resource(
            ResourceArn=arn,
            Tags=[
                {'Key': 'Environment', 'Value': 'Production'},
                {'Key': 'Team', 'Value': 'CloudOps'}
            ]
        )
    return {
        'PhysicalResourceId': f'{arn}-TagApplied'
    }



import boto3
import os

def lambda_handler(event, context):
    config = boto3.client('config')
    rule_arn = os.environ['CONFIG_RULE_ARN']

    tags = [
        {'Key': key.replace('TAG_', ''), 'Value': value}
        for key, value in os.environ.items()
        if key.startswith('TAG_')
    ]

    print(f"🧾 Tagging rule {rule_arn} with tags: {tags}")

    if event['RequestType'] == 'Create':
        config.tag_resource(
            ResourceArn=rule_arn,
            Tags=tags
        )

    return {
        'PhysicalResourceId': f'{rule_arn}-TagApplied'
    }
