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
backup_client = boto3.client("backup", region_name=region)
cloudwatch_logs = boto3.client("logs", region_name=region)
rds_client = boto3.client("rds", region_name=region)

# Constants
LOG_GROUP_NAME = "/HCOPS/AWS/SSM/EC2-ORR"
RETENTION_DAYS = 7
RESOURCE_TYPES = ["RDS"]  # Only fetching RDS resource tags for now
STATES = ["FAILED", "ABORTED", "EXPIRED"]  # Filter states


def fetch_support_team(resource_arn):
    """Fetch the Support-Team tag for the given RDS resource."""
    try:
        tags_response = rds_client.list_tags_for_resource(ResourceName=resource_arn)
        tags_list = tags_response.get("TagList", [])
        # Extract the Support-Team tag
        support_team = next((tag["Value"] for tag in tags_list if tag["Key"] == "Support-Team"), "N/A")
        return support_team
    except Exception as e:
        logging.error(f"Error fetching tags for resource {resource_arn}: {str(e)}")
        return "N/A"


def script_handler(event, context):
    global region
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

        # Filter for today's date
        start_time = datetime.utcnow() - timedelta(days=14)

        # Iterate through each resource type
        for resource_type in RESOURCE_TYPES:
            # Iterate through each state
            for state in STATES:
                response = backup_client.list_backup_jobs(
                    ByAccountId="*",
                    ByState=state,
                    ByResourceType=resource_type,
                    ByCreatedAfter=start_time,  # Filter jobs created today
                )

                # Process each job
                for job in response.get("BackupJobs", []):
                    # Extract job details
                    account_id = job.get("AccountId", "N/A")
                    resource_name = job.get("ResourceName", "N/A")
                    resource_arn = job.get("ResourceArn", "N/A")
                    job_id = job.get("BackupJobId", "N/A")
                    status = job.get("State", "N/A")
                    message = job.get("StatusMessage", "N/A")

                    # Fetch DB Instance details to get the correct ARN
                    try:
                        db_instance = rds_client.describe_db_instances(DBInstanceIdentifier=resource_name)
                        db_instance_arn = db_instance["DBInstances"][0]["DBInstanceArn"]
                        support_team = fetch_support_team(db_instance_arn)
                    except Exception as db_error:
                        logging.error(f"Error describing DB Instance {resource_name}: {str(db_error)}")
                        support_team = "N/A"

                    # Construct log message
                    log_message = (
                        f"account id: {account_id}, Resource Name: {resource_name}, "
                        f"Resource ARN: {db_instance_arn}, Status: {status}, "
                        f"Job ID: {job_id}, Support-Team: {support_team}, Region: {region}"
                    )

                    logging.info(f"Logging job status: {log_message}")

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

    except Exception as e:
        logging.error(
            f"An error occurred while processing backup jobs: {str(e)}\n{traceback.format_exc()}"
        )
        raise  # Optionally re-raise the exception to propagate it further
