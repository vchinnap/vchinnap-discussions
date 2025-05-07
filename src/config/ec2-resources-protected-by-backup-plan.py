import boto3
from datetime import datetime, timezone, timedelta

config = boto3.client('config')
ec2 = boto3.client('ec2')

def lambda_handler(event, context):
    result_token = event.get('resultToken', 'TESTMODE')
    evaluations = []

    # Get all EC2s with ConfigRule=True tag
    response = ec2.describe_instances(
        Filters=[
            {'Name': 'tag:ConfigRule', 'Values': ['True']}
        ]
    )

    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instance_id = instance['InstanceId']
            timestamp = instance['LaunchTime']

            # Default state: non-compliant
            compliance_type = 'NON_COMPLIANT'
            annotation = "Missing or incorrect snapshot_required tag"

            # Check snapshot_required tag
            tags = {tag['Key']: tag['Value'].lower() for tag in instance.get('Tags', [])}
            snapshot_required = tags.get('snapshot_required', '')

            if snapshot_required == 'yes':
                root_device_name = instance.get('RootDeviceName')
                block_devices = instance.get('BlockDeviceMappings', [])
                root_volume_id = None

                for device in block_devices:
                    if device['DeviceName'] == root_device_name and 'Ebs' in device:
                        root_volume_id = device['Ebs']['VolumeId']
                        break

                if root_volume_id:
                    snapshots = ec2.describe_snapshots(
                        Filters=[{'Name': 'volume-id', 'Values': [root_volume_id]}],
                        OwnerIds=['self']
                    )['Snapshots']

                    if snapshots:
                        latest_snapshot = max(snapshots, key=lambda x: x['StartTime'])
                        now = datetime.now(timezone.utc)

                        if latest_snapshot['StartTime'] >= now - timedelta(days=1):
                            compliance_type = 'COMPLIANT'
                            annotation = f"Snapshot found: {latest_snapshot['SnapshotId']} on {latest_snapshot['StartTime']}"
                        else:
                            annotation = f"No recent snapshot for root volume {root_volume_id}"
                    else:
                        annotation = f"No snapshots found for root volume {root_volume_id}"
                else:
                    annotation = f"Could not find root volume for instance {instance_id}"
            else:
                annotation = f"Tag 'snapshot_required' is missing or not 'yes'"

            evaluations.append({
                'ComplianceResourceType': 'AWS::EC2::Instance',
                'ComplianceResourceId': instance_id,
                'ComplianceType': compliance_type,
                'Annotation': annotation,
                'OrderingTimestamp': timestamp
            })

    if result_token != 'TESTMODE' and evaluations:
        config.put_evaluations(
            Evaluations=evaluations,
            ResultToken=result_token
        )

    return {
        'status': 'completed',
        'evaluated': len(evaluations)
    }
