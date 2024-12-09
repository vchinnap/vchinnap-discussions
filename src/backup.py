import boto3

def script_handler(event, context):
    # Initialize the AWS Backup client
    client = boto3.client('backup')
    
    try:
        # List backup jobs
        response = client.list_backup_jobs()
        
        # Print all jobs to CloudWatch logs
        for job in response['BackupJobs']:
            print(f"Backup Job ID: {job['BackupJobId']}")
            print(f"Status: {job['State']}")
            print(f"Resource Name: {job.get('ResourceName', 'N/A')}")
            print(f"Resource Type: {job.get('ResourceType', 'N/A')}")
            print(f"Creation Time: {job['CreationDate']}")
            print("-" * 40)
        
        # Return a structured response
        return {
            "statusCode": 200,
            "body": {
                "message": "Backup jobs listed successfully",
                "jobs": [
                    {
                        "BackupJobId": job['BackupJobId'],
                        "Status": job['State'],
                        "ResourceName": job.get('ResourceName', 'N/A'),
                        "ResourceType": job.get('ResourceType', 'N/A'),
                        "CreationTime": str(job['CreationDate']),
                    }
                    for job in response['BackupJobs']
                ]
            }
        }
    
    except Exception as e:
        print(f"Error listing backup jobs: {e}")
        return {
            "statusCode": 500,
            "body": {
                "message": f"Error listing backup jobs: {str(e)}"
            }
        }
