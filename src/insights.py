import boto3
import time

def script_handler(event, context):
    """
    AWS Lambda handler to execute a CloudWatch Logs Insights query.

    Parameters:
        event (dict): Event data passed to the Lambda function.
        context (LambdaContext): Context object provided by AWS Lambda.

    Returns:
        dict: The results of the CloudWatch Logs Insights query.
    """
    client = boto3.client('logs')

    # Extract parameters from the event
    log_group_name = event.get('log_group_name', '/aws/your-log-group-name')
    time_range = event.get('time_range', 3600)  # Default: Last 1 hour
    query_string = event.get('query_string', """
    fields @timestamp, @message
    | parse @message /Resource Name: (?<resource_name>[^,]+), Resource ID: (?<resource_id>[^,]+), Status: (?<status>[^,]+), Job ID: (?<job_id>[^,]+), Resource Type: (?<resource_type>[^,]+), Message: (?<error_message>.+)/
    | filter status = "FAILED" and resource_type = "RDS"
    | sort @timestamp desc
    | display @timestamp, resource_name, resource_id, status, job_id, resource_type, error_message
    | limit 50
    """)

    # Define the time range
    end_time = int(time.time() * 1000)  # Current time in milliseconds
    start_time = end_time - (time_range * 1000)  # Start time

    try:
        # Start the query
        response = client.start_query(
            logGroupName=log_group_name,
            startTime=start_time,
            endTime=end_time,
            queryString=query_string
        )
        query_id = response['queryId']
        print(f"Started query with ID: {query_id}")

        # Poll for query results
        while True:
            result = client.get_query_results(queryId=query_id)
            status = result['status']

            if status == 'Running':
                print("Query is running...")
            elif status == 'Complete':
                print("Query completed successfully.")
                results = []
                for row in result['results']:
                    data = {col['field']: col['value'] for col in row}
                    results.append(data)
                return {
                    "status": "success",
                    "results": results
                }
            elif status == 'Scheduled':
                print("Query is scheduled. Waiting for execution...")
            else:
                raise Exception(f"Query failed with status: {status}")

            time.sleep(2)  # Wait 2 seconds before checking again

    except Exception as e:
        print(f"Error: {e}")
        return {
            "status": "error",
            "message": str(e)
        }
