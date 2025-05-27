

import boto3
import os
import json
import urllib3

config = boto3.client('config')
http = urllib3.PoolManager()

def send_response(event, context, status, data, physical_resource_id=None, reason=None):
    response_url = event['ResponseURL']

    body = {
        'Status': status,
        'Reason': reason or f'See CloudWatch log stream: {context.log_stream_name}',
        'PhysicalResourceId': physical_resource_id or context.log_stream_name,
        'StackId': event['StackId'],
        'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'],
        'NoEcho': False,
        'Data': data
    }

    json_body = json.dumps(body)
    headers = {
        'content-type': '',
        'content-length': str(len(json_body))
    }

    try:
        response = http.request('PUT', response_url, body=json_body.encode('utf-8'), headers=headers)
        print(f"✅ Sent CloudFormation response: {response.status}")
    except Exception as e:
        print(f"❌ Failed to send CloudFormation response: {str(e)}")


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
            print("🔁 Update event — no tag changes applied.")

        elif request_type == 'Delete':
            print("🧹 Delete event — skipping tag removal for safety.")

        send_response(event, context, "SUCCESS", {}, physical_resource_id=f"{arn}-TagApplied" if arn else physical_id)

    except Exception as e:
        print("❌ Exception occurred:", str(e))
        send_response(event, context, "FAILED", {"Message": str(e)}, physical_resource_id=physical_id)





























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
