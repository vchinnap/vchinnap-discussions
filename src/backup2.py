import boto3
import time
import logging

# Initialize logging
logging.basicConfig(level=logging.INFO)

def script_handler(event, context):
    # Initialize AWS clients
    backup_client = boto3.client('backup')
    cloudwatch_logs = boto3.client('logs')

    # Define CloudWatch log group and stream
    log_group_name = "AWSBackupLogs"
    log_stream_name = "BackupJobStatus"

    try:
        # Fetch backup jobs
        response = backup_client.list_backup_jobs(
            ByState='FAILED',  # Filter for failed jobs
            ByResourceType='RDS'
        )

        # Iterate through backup jobs
        for job in response['BackupJobs']:
            # Extract details
            instance = f"Resource: {job.get('ResourceName', 'N/A')}"
            job_status = f"Status: {job['State']}"
            resource_type = f"Type: {job.get('ResourceType', 'N/A')}"
            backup_job_id = f"Job ID: {job['BackupJobId']}"
            message = f"Message: {job.get('StatusMessage', 'N/A')}"

            # Create a log row
            row = f"{instance} | {job_status} | {resource_type} | {backup_job_id} | {message}"
            logging.info(f"Logging row: {row}")

            # Log event
            log_event = {
                'timestamp': int(round(time.time() * 1000)),
                'message': row
            }

            # Push log event to CloudWatch
            cloudwatch_logs.put_log_events(
                logGroupName=log_group_name,
                logStreamName=log_stream_name,
                logEvents=[log_event]
            )

    except Exception as e:
        logging.error(f"An error occurred while logging backup jobs: {e}")
