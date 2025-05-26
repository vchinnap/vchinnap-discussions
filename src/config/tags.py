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
