import os
import boto3
from datetime import datetime, timezone

config = boto3.client("config")
ec2 = boto3.client("ec2")

def lambda_handler(event, context):
    result_token = event.get("resultToken", "TESTMODE")
    evaluations = []

    # Get all EC2s with ConfigRule=True tag
    response = ec2.describe_instances(
        Filters=[
            {"Name": "tag:ConfigRule", "Values": ["True"]}
        ]
    )

    # CloudWatch client (same region as Lambda)
    cloudwatch = boto3.client("cloudwatch")

    for reservation in response.get("Reservations", []):
        for instance in reservation.get("Instances", []):

            instance_id = instance["InstanceId"]
            timestamp = instance.get("LaunchTime", datetime.now(timezone.utc))

            compliance_type = "NON_COMPLIANT"
            annotation = "Missing CPUUtilization alarm"

            try:
                # Handle pagination
                paginator = cloudwatch.get_paginator("describe_alarms")

                for page in paginator.paginate(AlarmTypes=["MetricAlarm"]):
                    for alarm in page.get("MetricAlarms", []):

                        # Check namespace
                        if alarm.get("Namespace") != "AWS/EC2":
                            continue

                        # Check metric name
                        if alarm.get("MetricName") != "CPUUtilization":
                            continue

                        # Check dimensions
                        for d in alarm.get("Dimensions", []):
                            if d.get("Name") == "InstanceId" and d.get("Value") == instance_id:
                                compliance_type = "COMPLIANT"
                                annotation = "CPUUtilization alarm is present"
                                break

                        if compliance_type == "COMPLIANT":
                            break

                    if compliance_type == "COMPLIANT":
                        break

            except Exception as e:
                compliance_type = "NON_COMPLIANT"
                annotation = f"Error checking alarm: {str(e)[:200]}"

            evaluations.append(
                {
                    "ComplianceResourceType": "AWS::EC2::Instance",
                    "ComplianceResourceId": instance_id,
                    "ComplianceType": compliance_type,
                    "Annotation": annotation[:256],
                    "OrderingTimestamp": timestamp,
                }
            )

    # Submit to AWS Config
    if result_token != "TESTMODE" and evaluations:
        for i in range(0, len(evaluations), 100):
            config.put_evaluations(
                Evaluations=evaluations[i:i+100],
                ResultToken=result_token
            )

    return {
        "status": "completed",
        "evaluated_instances": len(evaluations)
    }
