import boto3
from datetime import datetime, timezone

config = boto3.client('config')
logs_client = boto3.client('logs')

def lambda_handler(event, context):
    result_token = event.get('resultToken', 'TESTMODE')
    evaluations = []

    paginator = logs_client.get_paginator('describe_log_groups')
    all_log_groups = []

    for page in paginator.paginate():
        for group in page['logGroups']:
            log_group_name = group['logGroupName']
            all_log_groups.append(log_group_name)

            # Focus only on log groups ending with '-tags' under Lambda namespace
            if log_group_name.startswith('/aws/lambda/') and log_group_name.endswith('-tags'):
                base_name = log_group_name.split('/')[-1].replace('-tags', '')

                # Check if Config Rule exists
                try:
                    config.describe_config_rules(ConfigRuleNames=[base_name])
                    compliance_type = 'COMPLIANT'
                    annotation = f"Matching Config rule '{base_name}' exists."
                except config.exceptions.NoSuchConfigRuleException:
                    compliance_type = 'NON_COMPLIANT'
                    annotation = f"No Config rule found for log group: {log_group_name}"

                evaluations.append({
                    'ComplianceResourceType': 'AWS::Logs::LogGroup',
                    'ComplianceResourceId': log_group_name,
                    'ComplianceType': compliance_type,
                    'Annotation': annotation,
                    'OrderingTimestamp': datetime.now(timezone.utc)
                })

    # Submit evaluations to AWS Config
    if result_token != 'TESTMODE' and evaluations:
        config.put_evaluations(
            Evaluations=evaluations,
            ResultToken=result_token
        )

    return {
        'status': 'completed',
        'evaluated': len(evaluations)
    }
