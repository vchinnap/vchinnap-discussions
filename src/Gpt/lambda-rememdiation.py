import boto3

# Initialize AWS Config Client
client = boto3.client('config')

# Specify the AWS Config Rule Name
config_rule_name = "<RULE_NAME>"

# Fetch Remediation Execution Details
response = client.describe_remediation_executions(
    ConfigRuleName=config_rule_name
)

# Process and Print Required Information
for execution in response['RemediationExecutions']:
    print(f"Resource ID: {execution['ResourceKey']['ResourceId']}")
    print(f"Resource Type: {execution['ResourceKey']['ResourceType']}")
    print(f"State: {execution['State']}")
    
    if 'StepDetails' in execution:
        for step in execution['StepDetails']:
            print(f"  - Step Name: {step.get('Name', 'N/A')}")
            print(f"    Step State: {step.get('State', 'N/A')}")
            print(f"    Step Message: {step.get('ErrorMessage', 'N/A')}")
            print(f"    Step Annotation: {step.get('RemediationType', 'N/A')}")
    
    print("-" * 40)
