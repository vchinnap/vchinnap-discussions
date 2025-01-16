import boto3
import os
import time
import logging
import traceback

# Initialize logging
logging.basicConfig(level=logging.INFO)

# AWS region and clients
region = os.environ["AWS_REGION"]
rds_client = boto3.client("rds", region_name=region)
cloudwatch_logs = boto3.client("logs", region_name=region)

# Constants
LOG_GROUP_NAME = "/HCOPS/AWS/SSM/EC2-ORR"
RETENTION_DAYS = 7


def fetch_support_team(db_instance):
    """Fetch the Support-Team tag for the given DB instance."""
    try:
        db_instance_arn = db_instance["DBInstanceArn"]
        tags_response = rds_client.list_tags_for_resource(ResourceName=db_instance_arn)
        tags_list = tags_response.get("TagList", [])
        
        # Extract the Support-Team tag
        support_team = next((tag["Value"] for tag in tags_list if tag["Key"] == "Support-Team"), "N/A")
        return support_team
    except Exception as e:
        logging.error(f"Error fetching Support-Team tag for DBInstanceArn {db_instance['DBInstanceArn']}: {str(e)}")
        return "N/A"


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
                # Describe the DB instance to get its details
                response = rds_client.describe_db_instances(DBInstanceIdentifier=resource_id)
                db_instance = response["DBInstances"][0]

                # Fetch the Support-Team tag
                support_team = fetch_support_team(db_instance)

                # Construct log message
                log_message = (
                    f"Resource ID: {resource_id}, DBInstanceArn: {db_instance['DBInstanceArn']}, "
                    f"Support-Team: {support_team}, Region: {region}"
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
