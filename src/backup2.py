import boto3
import os
import time
import logging
import traceback

# Initialize logging
logging.basicConfig(level=logging.INFO)

# AWS region and clients
region = os.environ.get("AWS_REGION", "us-east-1")
backup_client = boto3.client("backup", region_name=region)
cloudwatch_logs = boto3.client("logs", region_name=region)

# Constants
LOG_GROUP_NAME = "/aws/backup-status"
RETENTION_DAYS = 7


def script_handler(event, context):
    try:
        # Define log stream with a timestamp
        log_stream_name = f"backup-job-status-{time.strftime('%Y-%m-%d-%H-%M-%S')}"

        # Check if log group exists; create it if not
        log_groups = cloudwatch_logs.describe_log_groups(
            logGroupNamePrefix=LOG_GROUP_NAME
        )

        if not any(lg["logGroupName"] == LOG_GROUP_NAME for lg in log_groups["logGroups"]):
            cloudwatch_logs.create_log_group(logGroupName=LOG_GROUP_NAME)
            cloudwatch_logs.put_retention_policy(
                logGroupName=LOG_GROUP_NAME, retentionInDays=RETENTION_DAYS
            )

        # Create log stream
        cloudwatch_logs.create_log_stream(
            logGroupName=LOG_GROUP_NAME, logStreamName=log_stream_name
        )

        # Fetch backup jobs (filtering for failed RDS backup jobs)
        response = backup_client.list_backup_jobs(
            ByState="FAILED", ByResourceType="RDS"
        )

        # Iterate through backup jobs
        for job in response.get("BackupJobs", []):
            # Extract job details
            resource_name = job.get("ResourceName", "N/A")
            status = job.get("State", "N/A")
            job_id = job.get("BackupJobId", "N/A")
            resource_type = job.get("ResourceType", "N/A")
            message = job.get("StatusMessage", "N/A")

            # Create a log message
            log_message = (
                f"Resource: {resource_name}, Status: {status}, "
                f"Job ID: {job_id}, Resource Type: {resource_type}, "
                f"Message: {message}"
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
