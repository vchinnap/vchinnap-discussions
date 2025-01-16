import boto3
import os
import time
import logging
import traceback
from datetime import datetime, timedelta

# Initialize logging
logging.basicConfig(level=logging.INFO)

# AWS region and clients
region = os.environ["AWS_REGION"]
rds_client = boto3.client("rds", region_name=region)
cloudwatch_logs = boto3.client("logs", region_name=region)

# Constants
LOG_GROUP_NAME = "/HCOPS/AWS/SSM/EC2-ORR"
RETENTION_DAYS = 7


def fetch_support_team(resource_id):
    """Fetch the Support-Team tag for the given RDS resource using its ID."""
    try:
        # Describe the DB instance to get its ARN
        response = rds_client.describe_db_instances(DBInstanceIdentifier=resource_id)
        db_instance = response["DBInstances"][0]
        db_instance_arn = db_instance["DBInstanceArn"]

        # Fetch tags for the resource ARN
        tags_response = rds_client.list_tags_for_resource(ResourceName=db_instance_arn)
        tags_list = tags_response.get("TagList", [])
        
        # Extract the Support-Team tag
        support_team = next((tag["Value"] for tag in tags_list if tag["Key"] == "Support-Team"), "N/A")
        return support_team, db_instance_arn
    except Exception as e:
        logging.error(f"Error fetching Support-Team tag for resource {resource_id}: {str(e)}")
        return "N/A", None


def script_handler(event, context):
    try:
        # Define log stream with a timestamp
        log_stream_name = f"backup-job-status-{region}-{time.strftime('%Y-%m-%d-%H-%M-%S')}"
        
        # Check if log group exists; create it if not
        log_groups = cloudwatch_logs.describe_log_groups(logGroupNamePrefix=LOG_GROUP_NAME)
        if not any(lg["logGroupName"] == LOG_GROUP_NAME for lg in log_groups["logGroups"]):
            cloudwatch_logs.create_log_group(logGroupName=LOG_GROUP_NAME)
            cloudwatch_logs.put_retention_policy(
                logGroupName=LOG_GROUP_NAME, retentionInDays=RETENTION_DAYS
            )

        # Create log stream
        cloudwatch_logs.create_log_stream(
            logGroupName=LOG_GROUP_NAME, logStreamName=log_stream_name
        )

        # Retrieve resource IDs from the event
        resource_ids = event.get("RDSIDs", [])  # Replace with actual input key
        for resource_id in resource_ids:
            try:
                # Fetch the Support-Team tag and DBInstanceArn
                support_team, db_instance_arn = fetch_support_team(resource_id)

                # Construct log message
                log_message = (
                    f"Resource ID: {resource_id}, Support-Team: {support_team}, "
                    f"DBInstanceArn: {db_instance_arn or 'N/A'}, Region: {region}"
                )
                logging.info(log_message)

                # Log to CloudWatch
                log_event = {
                    "timestamp": int(round(time.time() * 1000)),
                    "message": log_message,
                }
                cloudwatch_logs.put_log_events(
                    logGroupName=LOG_GROUP_NAME,
                    logStreamName=log_stream_name,
                    logEvents=[log_event],
                )

            except Exception as db_error:
                logging.error(f"Error processing resource {resource_id}: {str(db_error)}")

    except Exception as e:
        logging.error(
            f"An error occurred while processing resources: {str(e)}\n{traceback.format_exc()}"
        )
        raise  # Optionally re-raise the exception to propagate it further
