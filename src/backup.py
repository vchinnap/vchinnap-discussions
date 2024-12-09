import boto3
from datetime import datetime

def script_handler(event, context):
    # Initialize the AWS Backup client
    client = boto3.client('backup')
    
    # Define statuses to filter
    statuses = ['FAILED', 'ABORTED', 'EXPIRED']
    
    # Fetch backup jobs with specific statuses
    backup_jobs = fetch_backup_jobs(client, statuses)
    
    # Print job details to Lambda logs
    print_job_details(backup_jobs)

    # Return results for testing/debugging
    return {
        "statusCode": 200,
        "body": {
            "backupJobs": [
                {
                    "BackupJobId": job.get('BackupJobId', 'N/A'),
                    "Status": job.get('State', 'N/A'),
                    "ResourceName": job.get('ResourceName', 'N/A'),
                    "Message": job.get('StatusMessage', 'N/A'),
                    "ResourceId": job.get('ResourceArn', 'N/A').split(':')[-1],
                    "ResourceType": job.get('ResourceType', 'N/A'),
                    "CreationTime": job.get('CreationDate', 'N/A').strftime('%Y-%m-%d %H:%M:%S')
                    if isinstance(job.get('CreationDate'), datetime) else 'N/A',
                }
                for job in backup_jobs
            ]
        }
    }

# Helper function to fetch backup jobs
def fetch_backup_jobs(client, statuses):
    try:
        response = client.list_backup_jobs()
        jobs = response['BackupJobs']
        # Filter jobs by status
        return [job for job in jobs if job['State'] in statuses]
    except Exception as e:
        print(f"Error fetching backup jobs: {str(e)}")
        return []

# Helper function to print job details
def print_job_details(jobs):
    print(f"{'BackupJobId':<40} {'Status':<10} {'ResourceName':<20} {'Message':<20} {'ResourceId':<20} {'ResourceType':<15} {'CreationTime':<25}")
    print("=" * 160)
    for job in jobs:
        job_id = job.get('BackupJobId', 'N/A')
        status = job.get('State', 'N/A')
        resource_name = job.get('ResourceName', 'N/A')
        message = job.get('StatusMessage', 'N/A')
        resource_id = job.get('ResourceArn', 'N/A').split(':')[-1]
        resource_type = job.get('ResourceType', 'N/A')
        creation_time = job.get('CreationDate', 'N/A').strftime('%Y-%m-%d %H:%M:%S') if isinstance(job.get('CreationDate'), datetime) else 'N/A'
        
        print(f"{job_id:<40} {status:<10} {resource_name:<20} {message:<20} {resource_id:<20} {resource_type:<15} {creation_time:<25}")
