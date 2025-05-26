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
