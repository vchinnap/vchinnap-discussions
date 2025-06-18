import boto3
from datetime import datetime, timezone

config = boto3.client('config')
logs_client = boto3.client('logs')

def lambda_handler(event, context):
    result_token = event.get('resultToken', 'TESTMODE')
    evaluations = []

    # ✅ Filter only for log groups starting with /aws/lambda/hcops-
    paginator = logs_client.get_paginator('describe_log_groups')

    for page in paginator.paginate(logGroupNamePrefix='/aws/lambda/hcops-'):
        for group in page['logGroups']:
            log_group_name = group['logGroupName']

            # ✅ Further restrict to only those ending with -tags
            if not log_group_name.endswith('-tags'):
                continue

            # Get tags for the log group
            try:
                tags = logs_client.list_tags_log_group(logGroupName=log_group_name).get('tags', {})
            except Exception as e:
                print(f"Could not fetch tags for {log_group_name}: {e}")
                continue

            # Filter only log groups with tag ConfigRule=True
            if tags.get('ConfigRule') != 'True':
                continue

            # Extract base name of the rule
            base_name = log_group_name.split('/')[-1].replace('-tags', '')

            # Check if Config rule exists
            try:
                config.describe_config_rules(ConfigRuleNames=[base_name])
                compliance_type = 'COMPLIANT'
                annotation = f"Config rule '{base_name}' exists for tagged log group."
            except config.exceptions.NoSuchConfigRuleException:
                compliance_type = 'NON_COMPLIANT'
                annotation = f"Tagged log group '{log_group_name}' has no matching Config rule."

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
