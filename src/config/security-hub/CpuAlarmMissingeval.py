import boto3
import os
import datetime
import uuid
import json

ec2 = boto3.client('ec2')
cloudwatch = boto3.client('cloudwatch')
securityhub = boto3.client('securityhub')

def lambda_handler(event, context):
    region = os.environ['AWS_REGION']
    account_id = context.invoked_function_arn.split(":")[4]
    
    response = ec2.describe_instances(Filters=[
        {'Name': 'tag:ConfigRule', 'Values': ['True']}
    ])
    
    findings = []

    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instance_id = instance['InstanceId']
            instance_arn = f"arn:aws:ec2:{region}:{account_id}:instance/{instance_id}"
            launch_time = instance['LaunchTime'].isoformat() + "Z"

            # Default: non-compliant
            compliant = False

            alarms = cloudwatch.describe_alarms(AlarmTypes=['MetricAlarm'])['MetricAlarms']
            for alarm in alarms:
                dimensions = {d['Name']: d['Value'] for d in alarm.get('Dimensions', [])}
                if dimensions.get('InstanceId') == instance_id and alarm.get('MetricName') == 'CPUUtilization':
                    compliant = True
                    break

            if not compliant:
                findings.append({
                    "SchemaVersion": "2018-10-08",
                    "Id": str(uuid.uuid4()),
                    "ProductArn": os.environ["SECURITY_HUB_PRODUCT_ARN"],
                    "GeneratorId": os.environ["GENERATOR_ID"],
                    "AwsAccountId": account_id,
                    "Types": ["Software and Configuration Checks/AWS Security Best Practices"],
                    "CreatedAt": launch_time,
                    "UpdatedAt": datetime.datetime.utcnow().isoformat() + "Z",
                    "Severity": { "Label": os.environ["SEVERITY"] },
                    "Title": os.environ["COMPLIANCE_TITLE"],
                    "Description": os.environ["COMPLIANCE_DESCRIPTION"],
                    "Resources": [{
                        "Type": "AwsEc2Instance",
                        "Id": instance_arn,
                        "Partition": "aws",
                        "Region": region
                    }],
                    "Compliance": {
                        "Status": "FAILED",
                        "SecurityControlId": os.environ.get("SECURITY_CONTROL_ID", ""),
                        "RelatedRequirements": json.loads(os.environ.get("RELATED_REQUIREMENTS", "[]"))
                    },
                    "RecordState": "ACTIVE"
                })

    if findings:
        securityhub.batch_import_findings(Findings=findings)

    return {
        'status': 'completed',
        'findings_sent': len(findings)
    }
