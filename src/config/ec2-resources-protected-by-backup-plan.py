import boto3
from datetime import datetime, timezone, timedelta

config = boto3.client('config')
ec2 = boto3.client('ec2')

def lambda_handler(event, context):
    result_token = event.get('resultToken', 'TESTMODE')
    evaluations = []

    # Get all EC2s with tag ConfigRule=True
    response = ec2.describe_instances(
        Filters=[
            {'Name': 'tag:ConfigRule', 'Values': ['True']}
        ]
    )

    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instance_id = instance['InstanceId']
            timestamp = instance['LaunchTime']
            compliance_type = 'NON_COMPLIANT'
            annotation = ''
            root_volume_id = None

            # Fetch tags and root volume
            tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
            snapshot_required_tag = tags.get('snapshot_required')

            root_device_name = instance.get('RootDeviceName')
            block_devices = instance.get('BlockDeviceMappings', [])
            for device in block_devices:
                if device['DeviceName'] == root_device_name and 'Ebs' in device:
                    root_volume_id = device['Ebs']['VolumeId']
                    break

            # Validate tag presence and value
            if snapshot_required_tag is None:
                annotation = f"Tag 'snapshot_required' is missing (Root volume: {root_volume_id or 'not found'})"
            elif snapshot_required_tag != 'Yes':
                annotation = f"Tag 'snapshot_required' is not set to 'Yes' (Found: '{snapshot_required_tag}'; Root volume: {root_volume_id or 'not found'})"
            elif not root_volume_id:
                annotation = f"Root volume not found for instance {instance_id}"
            else:
                # Check snapshots for the root volume
                snapshots = ec2.describe_snapshots(
                    Filters=[{'Name': 'volume-id', 'Values': [root_volume_id]}],
                    OwnerIds=['self']
                )['Snapshots']

                if not snapshots:
                    annotation = f"No snapshots found for root volume {root_volume_id}"
                else:
                    latest_snapshot = max(snapshots, key=lambda x: x['StartTime'])
                    now = datetime.now(timezone.utc)

                    if latest_snapshot['StartTime'] >= now - timedelta(days=1):
                        compliance_type = 'COMPLIANT'
                        annotation = (
                            f"Snapshot found for root volume {root_volume_id}: "
                            f"{latest_snapshot['SnapshotId']} on {latest_snapshot['StartTime']}"
                        )
                    else:
                        annotation = (
                            f"Only outdated snapshots found for root volume {root_volume_id}. "
                            f"Latest: {latest_snapshot['SnapshotId']} on {latest_snapshot['StartTime']}"
                        )

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
