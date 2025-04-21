import boto3

def check_snapshot_required_tag(events, context):
    instance_id = events['InstanceId']
    ec2_client = boto3.client('ec2')

    try:
        response = ec2_client.describe_instances(InstanceIds=[instance_id])
        instance = response['Reservations'][0]['Instances'][0]

        # Check for Snapshot_Required=Yes tag
        tags = instance.get('Tags', [])
        for tag in tags:
            if tag['Key'] == 'Snapshot_Required' and tag['Value'] == 'Yes':
                return {'SnapshotRequired': True}

        return {'SnapshotRequired': False}

    except Exception as e:
        return {'Status': 'Failed', 'Error': str(e)}
