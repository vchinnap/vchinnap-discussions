import boto3
import botocore

boto_config = botocore.config.Config(
    retries={'max_attempts': 5, 'mode': 'standard'}
)

ec2 = boto3.client('ec2', config=boto_config)
cloudwatch = boto3.client('cloudwatch', config=boto_config)
config = boto3.client('config', config=boto_config)

MAX_CONFIG_BATCH_SIZE = 100

LINUX_METRICS = {'CPUUtilization', 'disk_used_percent', 'mem_used_percent', 'StatusCheckFailed'}
WINDOWS_METRICS = {
    'CPUUtilization',
    'LogicalDisk % Free Space C:',
    'LogicalDisk % Free Space D:',
    'LogicalDisk % Free Space E:',
    'Memory Available Bytes',
    'StatusCheckFailed'
}

RHEL_DISK_PATHS = ['/var', '/tmp', '/var/log', '/var/log/audit', '/home', '/opt', '/usr']
AMZ_LINUX_PATHS = ['/']

def get_instances_with_platform_and_ami():
    instance_map = {}
    try:
        response = ec2.describe_instances(
            Filters=[{'Name': 'tag:ConfigRule', 'Values': ['True']}]
        )
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                instance_id = instance['InstanceId']
                platform = instance.get('PlatformDetails', 'Linux/UNIX')
                ami_id = instance.get('ImageId')
                instance_map[instance_id] = {'platform': platform, 'ami_id': ami_id}
    except Exception as e:
        print(f"❌ Error fetching EC2 instances: {e}")
    return instance_map

def get_ami_name(ami_id):
    try:
        image = ec2.describe_images(ImageIds=[ami_id])['Images'][0]
        return image.get('Name', '').lower()
    except Exception as e:
        print(f"⚠️ Failed to fetch AMI name for {ami_id}: {e}")
        return ''

def chunk_evaluations(evaluations, chunk_size=100):
    for i in range(0, len(evaluations), chunk_size):
        yield evaluations[i:i + chunk_size]

def lambda_handler(event, context):
    result_token = event.get('resultToken', 'TESTMODE')
    instance_map = get_instances_with_platform_and_ami()

    if not instance_map:
        print("ℹ️ No tagged instances found.")
        return {"message": "No matching EC2 instances."}

    evaluations = []
    total_alarms_matched = 0

    try:
        paginator = cloudwatch.get_paginator('describe_alarms')
        all_alarms = []
        for page in paginator.paginate(AlarmTypes=['MetricAlarm']):
            all_alarms.extend(page['MetricAlarms'])

        print(f"🔍 Total alarms fetched: {len(all_alarms)}")

        for instance_id, info in instance_map.items():
            platform = info['platform']
            ami_id = info['ami_id']
            platform_key = platform.lower()

            if 'windows' in platform_key:
                valid_metrics = WINDOWS_METRICS
                disk_alarm_names = {'LogicalDisk % Free Space C:', 'LogicalDisk % Free Space D:', 'LogicalDisk % Free Space E:'}
                matching_alarms = [
                    alarm for alarm in all_alarms
                    if any(d.get('Name') == 'InstanceId' and d.get('Value') == instance_id for d in alarm.get('Dimensions', []))
                    and alarm.get('MetricName') in valid_metrics
                ]
                print(f"🪟 Windows Instance {instance_id} → {len(matching_alarms)} matching alarms")
                total_alarms_matched += len(matching_alarms)

                for alarm in matching_alarms:
                    alarm_name = alarm['AlarmName']
                    metric = alarm.get('MetricName')
                    has_alarm = bool(alarm.get('AlarmActions'))
                    has_ok = bool(alarm.get('OKActions'))
                    has_insufficient = bool(alarm.get('InsufficientDataActions'))

                    if has_alarm and has_ok and has_insufficient:
                        compliance_type = 'COMPLIANT'
                        annotation = f"✅ Alarm '{metric}' has all required actions."
                    else:
                        compliance_type = 'NON_COMPLIANT'
                        missing = []
                        if not has_alarm: missing.append("ALARM")
                        if not has_ok: missing.append("OK")
                        if not has_insufficient: missing.append("INSUFFICIENT_DATA")
                        annotation = f"⚠️ Alarm '{metric}' is missing actions: {', '.join(missing)}"

                    evaluations.append({
                        'ComplianceResourceType': 'AWS::CloudWatch::Alarm',
                        'ComplianceResourceId': alarm_name,
                        'ComplianceType': compliance_type,
                        'Annotation': annotation,
                        'OrderingTimestamp': alarm['AlarmConfigurationUpdatedTimestamp']
                    })

            else:
                ami_name = get_ami_name(ami_id)
                required_paths = RHEL_DISK_PATHS if 'rhel' in ami_name or 'redhat' in ami_name else AMZ_LINUX_PATHS
                disk_path_status = {path: False for path in required_paths}

                matching_alarms = [
                    alarm for alarm in all_alarms
                    if any(d.get('Name') == 'InstanceId' and d.get('Value') == instance_id for d in alarm.get('Dimensions', []))
                    and alarm.get('MetricName') in LINUX_METRICS
                ]

                print(f"🐧 Linux Instance {instance_id} ({ami_name}) → {len(matching_alarms)} matching alarms")
                total_alarms_matched += len(matching_alarms)

                for alarm in matching_alarms:
                    alarm_name = alarm['AlarmName']
                    metric = alarm.get('MetricName')
                    dims = {d['Name']: d['Value'] for d in alarm.get('Dimensions', [])}
                    has_alarm = bool(alarm.get('AlarmActions'))
                    has_ok = bool(alarm.get('OKActions'))
                    has_insufficient = bool(alarm.get('InsufficientDataActions'))

                    # Track disk path coverage
                    if metric == 'disk_used_percent' and 'path' in dims:
                        path = dims['path']
                        if path in disk_path_status and has_alarm and has_ok and has_insufficient:
                            disk_path_status[path] = True

                    if has_alarm and has_ok and has_insufficient:
                        compliance_type = 'COMPLIANT'
                        annotation = f"✅ Alarm '{metric}' is fully configured."
                    else:
                        compliance_type = 'NON_COMPLIANT'
                        missing = []
                        if not has_alarm: missing.append("ALARM")
                        if not has_ok: missing.append("OK")
                        if not has_insufficient: missing.append("INSUFFICIENT_DATA")
                        annotation = f"⚠️ Alarm '{metric}' missing actions: {', '.join(missing)}"

                    evaluations.append({
                        'ComplianceResourceType': 'AWS::CloudWatch::Alarm',
                        'ComplianceResourceId': alarm_name,
                        'ComplianceType': compliance_type,
                        'Annotation': annotation,
                        'OrderingTimestamp': alarm['AlarmConfigurationUpdatedTimestamp']
                    })

                # Add overall NON_COMPLIANT if required paths are not covered
                missing_paths = [p for p, ok in disk_path_status.items() if not ok]
                if missing_paths:
                    annotation = f"⚠️ Missing disk_used_percent alarms for paths: {', '.join(missing_paths)}"
                    evaluations.append({
                        'ComplianceResourceType': 'AWS::EC2::Instance',
                        'ComplianceResourceId': instance_id,
                        'ComplianceType': 'NON_COMPLIANT',
                        'Annotation': annotation,
                        'OrderingTimestamp': context.timestamp if hasattr(context, 'timestamp') else None
                    })

    except Exception as e:
        print(f"❌ Error during alarm evaluation: {e}")
        return {"error": str(e)}

    # Submit evaluations
    if result_token != 'TESTMODE' and evaluations:
        for chunk in chunk_evaluations(evaluations, MAX_CONFIG_BATCH_SIZE):
            try:
                config.put_evaluations(Evaluations=chunk, ResultToken=result_token)
            except Exception as e:
                print(f"❌ Failed to submit evaluation chunk: {e}")

        print(f"✅ Submitted {len(evaluations)} evaluations.")

    return {
        "status": "completed",
        "instances_evaluated": len(instance_map),
        "alarms_evaluated": total_alarms_matched
    }

'''
import boto3
import botocore

boto_config = botocore.config.Config(
    retries={'max_attempts': 5, 'mode': 'standard'}
)

ec2 = boto3.client('ec2', config=boto_config)
cloudwatch = boto3.client('cloudwatch', config=boto_config)
config = boto3.client('config', config=boto_config)

MAX_CONFIG_BATCH_SIZE = 100

LINUX_METRICS = {
    'CPUUtilization',
    'disk_used_percent',
    'mem_used_percent',
    'StatusCheckFailed'
}

WINDOWS_METRICS = {
    'CPUUtilization',
    'LogicalDisk % Free Space C:',
    'LogicalDisk % Free Space D:',
    'LogicalDisk % Free Space E:',
    'Memory Available Bytes',
    'StatusCheckFailed'
}

def get_tagged_instances_with_platform():
    instance_map = {}
    try:
        response = ec2.describe_instances(
            Filters=[{'Name': 'tag:ConfigRule', 'Values': ['True']}]
        )
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                instance_id = instance['InstanceId']
                platform = instance.get('PlatformDetails', 'Linux/UNIX')
                instance_map[instance_id] = platform
    except Exception as e:
        print(f"❌ Error fetching EC2 instances: {e}")
    return instance_map

def chunk_evaluations(evaluations, chunk_size=100):
    for i in range(0, len(evaluations), chunk_size):
        yield evaluations[i:i + chunk_size]

def lambda_handler(event, context):
    result_token = event.get('resultToken', 'TESTMODE')
    instance_map = get_tagged_instances_with_platform()

    if not instance_map:
        print("ℹ️ No instances found with tag ConfigRule=True.")
        return {"message": "No matching EC2 instances."}

    evaluations = []
    total_alarms_matched = 0

    try:
        # Fetch all alarms
        paginator = cloudwatch.get_paginator('describe_alarms')
        all_alarms = []
        for page in paginator.paginate(AlarmTypes=['MetricAlarm']):
            all_alarms.extend(page['MetricAlarms'])

        print(f"🔍 Total alarms fetched from CloudWatch: {len(all_alarms)}")

        for instance_id, platform in instance_map.items():
            platform_key = platform.lower()
            if 'windows' in platform_key:
                allowed_metrics = WINDOWS_METRICS
            else:
                allowed_metrics = LINUX_METRICS

            matching_alarms = [
                alarm for alarm in all_alarms
                if any(
                    d.get('Name') == 'InstanceId' and d.get('Value') == instance_id
                    for d in alarm.get('Dimensions', [])
                ) and alarm.get('MetricName') in allowed_metrics
            ]

            print(f"📦 Instance {instance_id} ({platform}) has {len(matching_alarms)} matching alarms")

            total_alarms_matched += len(matching_alarms)

            for alarm in matching_alarms:
                alarm_name = alarm['AlarmName']
                has_alarm = bool(alarm.get('AlarmActions'))
                has_ok = bool(alarm.get('OKActions'))
                has_insufficient = bool(alarm.get('InsufficientDataActions'))

                if has_alarm and has_ok and has_insufficient:
                    compliance_type = 'COMPLIANT'
                    annotation = "✅ All required alarm actions are configured."
                else:
                    compliance_type = 'NON_COMPLIANT'
                    missing = []
                    if not has_alarm: missing.append("ALARM")
                    if not has_ok: missing.append("OK")
                    if not has_insufficient: missing.append("INSUFFICIENT_DATA")
                    annotation = f"⚠️ Missing actions for: {', '.join(missing)}"

                evaluations.append({
                    'ComplianceResourceType': 'AWS::CloudWatch::Alarm',
                    'ComplianceResourceId': alarm_name,
                    'ComplianceType': compliance_type,
                    'Annotation': annotation,
                    'OrderingTimestamp': alarm['AlarmConfigurationUpdatedTimestamp']
                })

    except Exception as e:
        print(f"❌ Error during alarm evaluation: {e}")
        return {"error": str(e)}

    # Submit evaluations in chunks
    if result_token != 'TESTMODE' and evaluations:
        for chunk in chunk_evaluations(evaluations, MAX_CONFIG_BATCH_SIZE):
            try:
                config.put_evaluations(
                    Evaluations=chunk,
                    ResultToken=result_token
                )
            except Exception as e:
                print(f"❌ Failed to submit evaluation chunk: {e}")

        print(f"✅ Submitted {len(evaluations)} evaluations to AWS Config.")

    return {
        "status": "completed",
        "instances_evaluated": len(instance_map),
        "alarms_evaluated": total_alarms_matched
    }
'''

'''
import boto3
import botocore

# Retry-safe config
boto_config = botocore.config.Config(
    retries={'max_attempts': 5, 'mode': 'standard'}
)

ec2 = boto3.client('ec2', config=boto_config)
cloudwatch = boto3.client('cloudwatch', config=boto_config)
config = boto3.client('config', config=boto_config)

MAX_CONFIG_BATCH_SIZE = 100

def get_config_rule_instance_ids():
    instance_ids = []
    try:
        response = ec2.describe_instances(
            Filters=[{'Name': 'tag:ConfigRule', 'Values': ['True']}]
        )
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                instance_ids.append(instance['InstanceId'])
    except Exception as e:
        print(f"❌ Error fetching EC2 instances: {e}")
    return instance_ids

def chunk_evaluations(evaluations, chunk_size=100):
    for i in range(0, len(evaluations), chunk_size):
        yield evaluations[i:i + chunk_size]

def lambda_handler(event, context):
    result_token = event.get('resultToken', 'TESTMODE')
    instance_ids = get_config_rule_instance_ids()

    if not instance_ids:
        print("ℹ️ No instances found with tag ConfigRule=True.")
        return {"message": "No matching EC2 instances."}

    evaluations = []
    total_alarms_matched = 0

    try:
        # Fetch all alarms
        paginator = cloudwatch.get_paginator('describe_alarms')
        all_alarms = []
        for page in paginator.paginate(AlarmTypes=['MetricAlarm']):
            all_alarms.extend(page['MetricAlarms'])

        print(f"🔍 Total alarms fetched from CloudWatch: {len(all_alarms)}")

        for instance_id in instance_ids:
            matching_alarms = [
                alarm for alarm in all_alarms
                if any(
                    d.get('Name') == 'InstanceId' and d.get('Value') == instance_id
                    for d in alarm.get('Dimensions', [])
                )
            ]

            print(f"📦 Instance {instance_id} has {len(matching_alarms)} alarms")

            total_alarms_matched += len(matching_alarms)

            for alarm in matching_alarms:
                alarm_name = alarm['AlarmName']
                has_alarm = bool(alarm.get('AlarmActions'))
                has_ok = bool(alarm.get('OKActions'))
                has_insufficient = bool(alarm.get('InsufficientDataActions'))

                if has_alarm and has_ok and has_insufficient:
                    compliance_type = 'COMPLIANT'
                    annotation = "✅ All required alarm actions are configured."
                else:
                    compliance_type = 'NON_COMPLIANT'
                    missing = []
                    if not has_alarm: missing.append("ALARM")
                    if not has_ok: missing.append("OK")
                    if not has_insufficient: missing.append("INSUFFICIENT_DATA")
                    annotation = f"⚠️ Missing actions for: {', '.join(missing)}"

                evaluations.append({
                    'ComplianceResourceType': 'AWS::CloudWatch::Alarm',
                    'ComplianceResourceId': alarm_name,
                    'ComplianceType': compliance_type,
                    'Annotation': annotation,
                    'OrderingTimestamp': alarm['AlarmConfigurationUpdatedTimestamp']
                })

    except Exception as e:
        print(f"❌ Error during alarm evaluation: {e}")
        return {"error": str(e)}

    # Submit in chunks
    if result_token != 'TESTMODE' and evaluations:
        for chunk in chunk_evaluations(evaluations, MAX_CONFIG_BATCH_SIZE):
            try:
                config.put_evaluations(
                    Evaluations=chunk,
                    ResultToken=result_token
                )
            except Exception as e:
                print(f"❌ Failed to submit evaluation chunk: {e}")

        print(f"✅ Submitted {len(evaluations)} evaluations to AWS Config.")

    return {
        "status": "completed",
        "instances_evaluated": len(instance_ids),
        "alarms_evaluated": total_alarms_matched
    }

'''




'''
import boto3

ec2 = boto3.client('ec2')
cloudwatch = boto3.client('cloudwatch')

def get_config_rule_instances():
    instance_ids = []
    try:
        response = ec2.describe_instances(
            Filters=[{'Name': 'tag:ConfigRule', 'Values': ['True']}]
        )
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                instance_ids.append(instance['InstanceId'])
    except Exception as e:
        print(f"❌ Error fetching EC2 instances: {e}")
    return instance_ids

def get_alarms_for_instance(instance_id):
    matching_alarms = []
    try:
        paginator = cloudwatch.get_paginator('describe_alarms')
        for page in paginator.paginate(AlarmTypes=['MetricAlarm']):
            for alarm in page['MetricAlarms']:
                alarm_name = alarm['AlarmName']
                if alarm_name.startswith(instance_id):
                    matching_alarms.append(alarm_name)
    except Exception as e:
        print(f"❌ Error fetching alarms for {instance_id}: {e}")
    return matching_alarms

def lambda_handler(event, context):
    instance_ids = get_config_rule_instances()

    result = {}

    if not instance_ids:
        print("ℹ️ No instances found with tag ConfigRule=True")
        return {"message": "No instances found with tag ConfigRule=True"}

    for instance_id in instance_ids:
        alarms = get_alarms_for_instance(instance_id)
        print(f"\n🔍 Alarms for instance {instance_id}:")
        if alarms:
            for alarm in alarms:
                print(f" - {alarm}")
        else:
            print(" ⚠️ No matching alarms found.")
        result[instance_id] = alarms

    return {
        "status": "completed",
        "alarm_summary": result
    }

    '''


import boto3
import botocore

# Retry-safe configuration
boto_config = botocore.config.Config(
    retries={
        'max_attempts': 5,
        'mode': 'standard'
    }
)

ec2 = boto3.client('ec2', config=boto_config)
cloudwatch = boto3.client('cloudwatch', config=boto_config)
config = boto3.client('config', config=boto_config)

MAX_CONFIG_BATCH_SIZE = 100

def get_config_rule_instance_ids():
    instance_ids = []
    try:
        response = ec2.describe_instances(
            Filters=[{'Name': 'tag:ConfigRule', 'Values': ['True']}]
        )
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                instance_ids.append(instance['InstanceId'])
    except Exception as e:
        print(f"❌ Error fetching EC2 instances: {e}")
    return instance_ids

def chunk_evaluations(evaluations, chunk_size=100):
    for i in range(0, len(evaluations), chunk_size):
        yield evaluations[i:i + chunk_size]

def lambda_handler(event, context):
    result_token = event.get('resultToken', 'TESTMODE')
    instance_ids = get_config_rule_instance_ids()

    if not instance_ids:
        print("ℹ️ No instances found with tag ConfigRule=True.")
        return {"message": "No matching EC2 instances."}

    evaluations = []

    try:
        paginator = cloudwatch.get_paginator('describe_alarms')
        for page in paginator.paginate(AlarmTypes=['MetricAlarm']):
            for alarm in page['MetricAlarms']:
                alarm_name = alarm['AlarmName']

                # Filter: Only process alarms tied to tagged EC2s
                if not any(alarm_name.startswith(instance_id) for instance_id in instance_ids):
                    continue

                # Action checks
                has_alarm = bool(alarm.get('AlarmActions'))
                has_ok = bool(alarm.get('OKActions'))
                has_insufficient = bool(alarm.get('InsufficientDataActions'))

                if has_alarm and has_ok and has_insufficient:
                    compliance_type = 'COMPLIANT'
                    annotation = "✅ All required alarm actions are configured."
                else:
                    compliance_type = 'NON_COMPLIANT'
                    missing = []
                    if not has_alarm: missing.append("ALARM")
                    if not has_ok: missing.append("OK")
                    if not has_insufficient: missing.append("INSUFFICIENT_DATA")
                    annotation = f"⚠️ Missing actions for: {', '.join(missing)}"

                evaluations.append({
                    'ComplianceResourceType': 'AWS::CloudWatch::Alarm',
                    'ComplianceResourceId': alarm_name,
                    'ComplianceType': compliance_type,
                    'Annotation': annotation,
                    'OrderingTimestamp': alarm['AlarmConfigurationUpdatedTimestamp']
                })

    except Exception as e:
        print(f"❌ Error during alarm evaluation: {e}")
        return {"error": str(e)}

    # Submit evaluations in chunks
    if result_token != 'TESTMODE' and evaluations:
        for chunk in chunk_evaluations(evaluations, MAX_CONFIG_BATCH_SIZE):
            try:
                config.put_evaluations(
                    Evaluations=chunk,
                    ResultToken=result_token
                )
            except Exception as e:
                print(f"❌ Failed to submit evaluation chunk: {e}")

        print(f"✅ Submitted {len(evaluations)} evaluations to AWS Config.")

    return {
        "status": "completed",
        "evaluated_alarms": len(evaluations)
    }
