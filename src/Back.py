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
dynamodb_client = boto3.client("dynamodb", region_name=region)

# Constants
LOG_GROUP_NAME = "/HCOPS/AWS/SSM/EC2-ORR"
RETENTION_DAYS = 7
RESOURCE_TYPES = ["RDS", "DynamoDB", "Aurora"]  # Add other resource types as needed
STATES = ["FAILED", "ABORTED", "EXPIRED"]  # Filter states

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

        # Filter for the past 14 days
        start_time = datetime.utcnow() - timedelta(days=14)

        # Iterate through each resource type
        for resource_type in RESOURCE_TYPES:
            # Iterate through each state
            for state in STATES:
                response = backup_client.list_backup_jobs(
                    ByState=state,
                    ByResourceType=resource_type,
                    ByCreatedAfter=start_time,
                )

                # Process each job
                for job in response.get("BackupJobs", []):
                    # Extract job details
                    account_id = job.get("AccountId", "N/A")
                    resource_arn = job.get("ResourceArn", "N/A")
                    resource_name = job.get("ResourceName", "N/A")
                    status = job.get("State", "N/A")
                    job_id = job.get("BackupJobId", "N/A")
                    message = job.get("StatusMessage", "N/A")
                    
                    # Initialize support_team
                    support_team = "N/A"
                    
                    # Fetch tags based on resource type
                    try:
                        if resource_type == "RDS" or resource_type == "Aurora":
                            tags_response = rds_client.list_tags_for_resource(ResourceName=resource_arn)
                            tags = tags_response.get("TagList", [])
                        elif resource_type == "DynamoDB":
                            tags_response = dynamodb_client.list_tags_of_resource(ResourceArn=resource_arn)
                            tags = tags_response.get("Tags", [])
                        else:
                            tags = []

                        # Extract Support-Team tag
                        support_team = next((tag["Value"] for tag in tags if tag["Key"] == "Support-Team"), "N/A")
                    except Exception as tag_error:
                        logging.error(f"Error fetching tags for resource {resource_arn}: {str(tag_error)}")
                    
                    # Construct log message
                    log_message = (
                        f"Account ID: {account_id}, Resource Name: {resource_name}, "
                        f"Resource ARN: {resource_arn}, Status: {status}, "
                        f"Job ID: {job_id}, Resource Type: {resource_type}, "
                        f"Message: {message}, Support Team: {support_team}, Region: {region}"
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
