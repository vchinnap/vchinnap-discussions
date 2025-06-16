import boto3
import json
import os

logs_client = boto3.client('logs')

def lambda_handler(event, context):
    # Extract rule name from the CloudTrail event
    try:
        rule_name = event['detail']['requestParameters']['configRuleName']
        log_group_name = f"/aws/lambda/{rule_name}-tags"

        # Delete the log group
        response = logs_client.delete_log_group(logGroupName=log_group_name)
        print(f"Deleted log group: {log_group_name}")
        return {
            'statusCode': 200,
            'body': f"Successfully deleted log group: {log_group_name}"
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': f"Failed to delete log group: {str(e)}"
        }
