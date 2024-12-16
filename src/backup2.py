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
            resource_id = job.get("ResourceArn", "N/A").split(":")[-1]  # Extract the Resource ID from ARN
            status = job.get("State", "N/A")
            job_id = job.get("BackupJobId", "N/A")
            resource_type = job.get("ResourceType", "N/A")
            message = job.get("StatusMessage", "N/A")

            # Add resource_name and resource_id in log message
            log_message = (
                f"Resource Name: {resource_name}, Resource ID: {resource_id}, Status: {status}, "
                f"Job ID: {job_id}, Resource Type: {resource_type}, Message: {message}"
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




















import boto3
import os
import time
import logging
import traceback

# Initialize logging
logging.basicConfig(level=logging.INFO)

# AWS region fetched dynamically
region = os.environ.get("AWS_REGION", "us-east-1")
backup_client = boto3.client("backup", region_name=region)
cloudwatch_logs = boto3.client("logs", region_name=region)

# Constants
LOG_GROUP_NAME = "/aws/backup-status"
RETENTION_DAYS = 7
RESOURCE_TYPES = ["RDS", "AURORA", "DYNAMODB"]
STATES = ["FAILED", "ABORTED", "EXPIRED"]

def script_handler(event, context):
    try:
        logging.info(f"Processing AWS Region: {region}")

        # Define log stream with a timestamp
        log_stream_name = f"backup-job-status-{region}-{time.strftime('%Y-%m-%d-%H-%M-%S')}"

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

        # Iterate through resource types and states
        for resource_type in RESOURCE_TYPES:
            for state in STATES:
                try:
                    logging.info(f"Fetching jobs for ResourceType: {resource_type}, State: {state}")
                    
                    response = backup_client.list_backup_jobs(
                        ByState=state, ByResourceType=resource_type
                    )

                    # Process each job
                    for job in response.get("BackupJobs", []):
                        resource_name = job.get("ResourceName", "N/A")
                        resource_id = job.get("ResourceArn", "N/A").split(":")[-1]
                        status = job.get("State", "N/A")
                        job_id = job.get("BackupJobId", "N/A")
                        resource_type = job.get("ResourceType", "N/A")
                        message = job.get("StatusMessage", "N/A")

                        # Log message
                        log_message = (
                            f"Region: {region}, Resource Name: {resource_name}, Resource ID: {resource_id}, "
                            f"Status: {status}, Job ID: {job_id}, Resource Type: {resource_type}, Message: {message}"
                        )
                        logging.info(log_message)

                        # Push to CloudWatch Logs
                        log_event = {
                            "timestamp": int(round(time.time() * 1000)),
                            "message": log_message,
                        }
                        cloudwatch_logs.put_log_events(
                            logGroupName=LOG_GROUP_NAME,
                            logStreamName=log_stream_name,
                            logEvents=[log_event],
                        )

                except Exception as fetch_error:
                    logging.error(f"Error fetching jobs for {resource_type} in {region}: {str(fetch_error)}")

    except Exception as e:
        logging.error(
            f"An error occurred while processing backup jobs: {str(e)}\n{traceback.format_exc()}"
        )
        raise  # Re-raise to propagate the exception

