import boto3
import time

# Initialize the CloudWatch Logs client
client = boto3.client('logs')

# Define the query
log_group = '/aws/lambda/your-log-group-name'  # Replace with your log group
query = """
fields @timestamp, @message
| sort @timestamp desc
| limit 20
"""

# Start the query
response = client.start_query(
    logGroupName=log_group,
    startTime=int((time.time() - 3600) * 1000),  # Last 1 hour
    endTime=int(time.time() * 1000),            # Current time
    queryString=query
)

query_id = response['queryId']

# Wait for the query results
status = 'Running'
while status == 'Running':
    result = client.get_query_results(queryId=query_id)
    status = result['status']
    time.sleep(1)  # Wait 1 second between status checks

# Print the results
if status == 'Complete':
    for row in result['results']:
        print({col['field']: col['value'] for col in row})

else:
    print("Query failed or timed out.")
