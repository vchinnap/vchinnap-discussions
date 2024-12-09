import boto3
from datetime import datetime

# Initialize the AWS Backup client
client = boto3.client('backup')

# Fetch backup jobs with specific statuses
def fetch_backup_jobs(statuses):
    response = client.list_backup_jobs()
    jobs = response['BackupJobs']
    
    # Filter jobs by status
    filtered_jobs = [job for job in jobs if job['State'] in statuses]
    
    return filtered_jobs

# Print details for each job
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

if __name__ == "__main__":
    statuses = ['FAILED', 'ABORTED', 'EXPIRED']
    backup_jobs = fetch_backup_jobs(statuses)
    print_job_details(backup_jobs)
