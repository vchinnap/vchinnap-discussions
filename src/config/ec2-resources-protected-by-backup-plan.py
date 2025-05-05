import json
import boto3
import datetime

# Initialize AWS clients for Config, Backup, and EC2.
config_client = boto3.client('config')
backup_client = boto3.client('backup')
ec2_client = boto3.client('ec2')

def lambda_handler(event, context):
    """
    This Lambda function is triggered periodically by AWS Config.
    It filters EC2 instances based on the tag: ConfigRule=True,
    checks whether each protected instance is part of an AWS Backup plan,
    and finally reports these evaluations back to AWS Config.
    """
    print("Received event: " + json.dumps(event))
    
    # For periodic triggers, the event MUST include a resultToken.
    result_token = event.get("resultToken")
    if not result_token:
        raise Exception("Missing resultToken in event payload.")

    evaluations = []  # List to hold evaluation results.
    
    # 1. Retrieve EC2 instances having tag ConfigRule=True.
    try:
        ec2_instance_ids = list_filtered_ec2_instances()
    except Exception as e:
        print("Error retrieving filtered EC2 instances: " + str(e))
        raise

    # 2. Retrieve the list of protected EC2 instances from AWS Backup.
    try:
        protected_instances = get_protected_instances()
    except Exception as e:
        print("Error retrieving protected instances: " + str(e))
        raise

    # Current timestamp (ISO8601 format) used as the ordering timestamp.
    now = datetime.datetime.utcnow().isoformat() + "Z"

    # 3. Evaluate each instance's compliance:
    #    - Mark as COMPLIANT if the instance is found in AWS Backup’s protection list.
    #    - Otherwise mark as NON_COMPLIANT.
    for instance_id in ec2_instance_ids:
        compliance_type = "COMPLIANT" if instance_id in protected_instances else "NON_COMPLIANT"
        evaluation = {
            "ComplianceResourceType": "AWS::EC2::Instance",
            "ComplianceResourceId": instance_id,
            "ComplianceType": compliance_type,
            "OrderingTimestamp": now
        }
        evaluations.append(evaluation)
        
    print("Prepared Evaluations: " + json.dumps(evaluations))
    
    # 4. Report the evaluations back to AWS Config using the provided resultToken.
    try:
        response = config_client.put_evaluations(
            Evaluations=evaluations,
            ResultToken=result_token
        )
        print("put_evaluations response: " + json.dumps(response))
    except Exception as e:
        print("Error putting evaluations: " + str(e))
        raise

    return response

def list_filtered_ec2_instances():
    """
    Uses the EC2 API (describe_instances) with a filter to obtain all EC2
    instances which have the tag 'ConfigRule' set to 'True'.
    """
    instance_ids = []
    paginator = ec2_client.get_paginator("describe_instances")
    page_iterator = paginator.paginate(
        Filters=[
            {"Name": "tag:ConfigRule", "Values": ["True"]}
        ]
    )
    
    for page in page_iterator:
        for reservation in page.get("Reservations", []):
            for instance in reservation.get("Instances", []):
                instance_ids.append(instance["InstanceId"])
    
    print("Filtered EC2 instance IDs: ", instance_ids)
    return instance_ids

def get_protected_instances():
    """
    Uses AWS Backup's list_protected_resources API to identify all protected resources.
    Filters the results to include only EC2 instances by checking the ARN format, and extracts their IDs.
    """
    protected_ids = set()
    next_token = None

    while True:
        params = {}
        if next_token:
            params["NextToken"] = next_token

        response = backup_client.list_protected_resources(**params)
        print("list_protected_resources response: " + json.dumps(response))

        # EC2 protected resource ARNs often look like:
        # arn:aws:ec2:region:account-id:instance/instance-id
        for resource in response.get("Results", []):
            arn = resource.get("resourceArn", "")
            if ":instance/" in arn:
                instance_id = arn.split("/")[-1]
                if instance_id:
                    protected_ids.add(instance_id)

        next_token = response.get("NextToken")
        if not next_token:
            break

    print("Protected EC2 instances: ", list(protected_ids))
    return protected_ids
