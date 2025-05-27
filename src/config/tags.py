import boto3
import os
import json
import cfnresponse

config = boto3.client('config')

def lambda_handler(event, context):
    print("📦 Received event:")
    print(json.dumps(event))

    request_type = event.get('RequestType')
    physical_id = event.get('PhysicalResourceId', 'TagCustomResourceDefault')
    arn = os.environ.get('CONFIG_RULE_ARN')

    try:
        if request_type == 'Create':
            print(f"🏷️ Applying tags to Config rule: {arn}")
            config.tag_resource(
                ResourceArn=arn,
                Tags=[
                    {'Key': 'Environment', 'Value': 'Production'},
                    {'Key': 'Team', 'Value': 'CloudOps'}
                ]
            )

        elif request_type == 'Update':
            print("🔁 Update event received. No action taken.")

        elif request_type == 'Delete':
            print("🧹 Delete event received. No tag removal performed for rollback safety.")

        # ✅ Always send SUCCESS with PhysicalResourceId
        cfnresponse.send(
            event, context, cfnresponse.SUCCESS,
            {}, physicalResourceId=f'{arn}-TagApplied' if arn else physical_id
        )

    except Exception as e:
        print("❌ Exception occurred:", str(e))
        # ❌ Send FAILURE to CloudFormation
        cfnresponse.send(
            event, context, cfnresponse.FAILED,
            {'Message': str(e)},
            physicalResourceId=physical_id
        )











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
