import boto3
from datetime import datetime

config = boto3.client('config')
ec2 = boto3.client('ec2')
cloudwatch = boto3.client('cloudwatch')

def lambda_handler(event, context):
    print(" Lambda execution started")

    result_token = event.get('resultToken', 'TESTMODE')
    evaluations = []
    ami_cache = {}
    allowed_namespaces = ['CWAgent', 'HCOPS/EDF']

    # Step 1: Get EC2s with ConfigRule=True
    try:
        response = ec2.describe_instances(
            Filters=[{'Name': 'tag:ConfigRule', 'Values': ['True']}]
        )
    except Exception as e:
        print(f" Error fetching EC2 instances: {e}")
        return

    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instance_id = instance['InstanceId']
            timestamp = instance['LaunchTime']
            image_id = instance['ImageId']
            platform = instance.get('PlatformDetails', '')

            print(f" Checking instance: {instance_id}, ImageId: {image_id}, Platform: {platform}")

            # Check platform
            if platform and 'linux' not in platform.lower():
                print(f"⏭ Skipping non-Linux platform: {platform}")
                continue

            # Resolve AMI name
            if image_id in ami_cache:
                ami_name = ami_cache[image_id]
            else:
                try:
                    image = ec2.describe_images(ImageIds=[image_id])['Images'][0]
                    ami_name = image.get('Name', '').lower()
                    ami_cache[image_id] = ami_name
                except Exception as e:
                    print(f"Error retrieving AMI name for {image_id}: {e}")
                    continue

            print(f" AMI Name: {ami_name}")

            # OS and Required Paths
            if 'rhel' in ami_name or 'redhat' in ami_name:
                os_flavor = 'Red Hat'
                required_paths = ['/', '/var', '/tmp', '/var/log', '/var/log/audit', '/home', '/opt', '/usr']
            elif 'amzn' in ami_name or 'al2' in ami_name:
                os_flavor = 'Amazon Linux'
                required_paths = ['/']
            else:
                print(f" Skipping unsupported AMI: {ami_name}")
                continue

            print(f" Required paths: {required_paths}")
            path_alarms = {path: False for path in required_paths}

            # Step 2: Use paginator to find disk_used_percent metrics
            try:
                paginator = cloudwatch.get_paginator('list_metrics')
                for namespace in allowed_namespaces:
                    print(f" Checking namespace: {namespace}")
                    for page in paginator.paginate(
                        Namespace=namespace,
                        MetricName='disk_used_percent',
                        Dimensions=[
                            {'Name': 'InstanceId', 'Value': instance_id}
                        ]
                    ):
                        for metric in page['Metrics']:
                            dims = {d['Name']: d['Value'] for d in metric['Dimensions']}
                            path = dims.get('path')
                            if path in path_alarms:
                                path_alarms[path] = True
                                print(f" Found metric for path: {path}")
            except Exception as e:
                print(f" Error listing metrics: {e}")
                continue

            # Step 3: Evaluate
            missing_paths = [path for path, found in path_alarms.items() if not found]
            if not missing_paths:
                compliance_type = 'COMPLIANT'
                annotation = f"{os_flavor}: All required disk_used_percent metrics are present."
            else:
                compliance_type = 'NON_COMPLIANT'
                annotation = f"{os_flavor}: Missing disk metrics for paths: {', '.join(missing_paths)}"

            print(f" RESULT: {instance_id} → {compliance_type} — {annotation}")

            evaluations.append({
                'ComplianceResourceType': 'AWS::EC2::Instance',
                'ComplianceResourceId': instance_id,
                'ComplianceType': compliance_type,
                'Annotation': annotation,
                'OrderingTimestamp': timestamp
            })

    # Step 4: Send to AWS Config
    if result_token != 'TESTMODE' and evaluations:
        try:
            config.put_evaluations(
                Evaluations=evaluations,
                ResultToken=result_token
            )
            print(" Evaluations submitted to AWS Config")
        except Exception as e:
            print(f" Error submitting evaluations: {e}")

    return {
        'status': 'completed',
        'evaluated': len(evaluations)
    }
