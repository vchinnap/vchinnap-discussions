import boto3
import csv
import io

# Initialize S3 client
s3_client = boto3.client('s3')

def read_csv_from_s3(bucket_name, file_key):
    """
    Reads a CSV file from S3 and prints its content.

    Args:
        bucket_name (str): The name of the S3 bucket.
        file_key (str): The key (path) of the CSV file in the bucket.
    """
    try:
        # Fetch the object from S3
        response = s3_client.get_object(Bucket=bucket_name, Key=file_key)

        # Read the content of the file
        csv_content = response['Body'].read().decode('utf-8')

        # Use csv.reader to parse the content
        csv_reader = csv.reader(io.StringIO(csv_content))
        for row in csv_reader:
            print(row)  # Print each row

    except Exception as e:
        print(f"Error reading CSV file from S3: {str(e)}")

if __name__ == "__main__":
    # Replace with your S3 bucket name and file key
    bucket_name = "your-bucket-name"
    file_key = "path/to/your-file.csv"

    read_csv_from_s3(bucket_name, file_key)
