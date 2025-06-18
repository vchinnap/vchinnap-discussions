import boto3

logs_client = boto3.client('logs')
config_client = boto3.client('config')

def lambda_handler(event, context):
    deleted_log_groups = []
    skipped_log_groups = []
    all_log_groups = []

    paginator = logs_client.get_paginator('describe_log_groups')
    for page in paginator.paginate():
        for group in page['logGroups']:
            log_group_name = group['logGroupName']
            all_log_groups.append(log_group_name)

            if log_group_name.startswith('/aws/lambda/') and log_group_name.endswith('-tags'):
                base_name = log_group_name.split('/')[-1].replace('-tags', '')

                # Check Config Rule existence
                try:
                    config_client.describe_config_rules(ConfigRuleNames=[base_name])
                    skipped_log_groups.append(log_group_name)  # Config rule exists
                except config_client.exceptions.NoSuchConfigRuleException:
                    # Safe to delete
                    logs_client.delete_log_group(logGroupName=log_group_name)
                    deleted_log_groups.append(log_group_name)

    return {
        'status': 'completed',
        'deleted': deleted_log_groups,
        'skipped': skipped_log_groups,
        'total_checked': len(all_log_groups)
    }
