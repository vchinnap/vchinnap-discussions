import boto3
import logging
import traceback

# Initialize logging
logging.basicConfig(level=logging.DEBUG)

# Replace with your AWS region
region = "us-east-1"  # Update to your region
backup_client = boto3.client('backup', region_name=region)

def get_backup_jobs(client):
    """
    Fetches backup jobs from the AWS Backup service.

    Args:
        client: An AWS Backup client object.

    Returns:
        A list of backup job dictionaries.
    """
    jobs = []
    try:
        # Initial API call
        response = client.list_backup_jobs()
        jobs.extend(response.get('BackupJobs', []))

        # Paginate through the results if 'NextToken' exists
        while 'NextToken' in response:
            response = client.list_backup_jobs(NextToken=response['NextToken'])
            jobs.extend(response.get('BackupJobs', []))
    except Exception as e:
        logging.error(f"Error fetching backup jobs: {str(e)}\n{traceback.format_exc()}")
        raise  # Re-raise the exception after logging it

    return jobs

def script_handler(event, context):
    """
    Main handler function to process AWS Backup jobs.

    Args:
        event: The event object.
        context: The context object.
    """
    try:
        logging.debug("Starting script_handler")
        jobs = get_backup_jobs(backup_client)

        # Process backup job information
        for job in jobs:
            try:
                account_id = job.get("AccountId", None)
                if not account_id:
                    logging.warning(f"Missing AccountId in job data: {job}")
                else:
                    logging.debug(f"Account ID: {account_id}")

                logging.debug(f"Job ID: {job.get('BackupJobId', 'N/A')}")
                logging.debug(f"Creation Date: {job.get('CreationDate', 'N/A')}")
                logging.debug(f"Status: {job.get('State', 'N/A')}")

                # Add any additional processing or logic here
            except Exception as job_error:
                logging.error(f"Error processing job: {str(job_error)}\nJob Data: {job}\n{traceback.format_exc()}")
                # Do not raise; allow processing of remaining jobs
    except Exception as e:
        logging.error(f"Error in script_handler: {str(e)}\n{traceback.format_exc()}")
        raise  # Re-raise the exception for debugging
