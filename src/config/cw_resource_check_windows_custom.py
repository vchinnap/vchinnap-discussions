import json
import boto3

def lambda_handler(event, context):
    config = boto3.client('config')
    cloudwatch = boto3.client('cloudwatch')
    ec2 = boto3.client('ec2')

    invoking_event = json.loads(event['invokingEvent'])
    configuration_item = invoking_event['configurationItem']
    instance_id = configuration_item['resourceId']

    # 1. Check instance tags
    tags = {tag['key']: tag['value'] for tag in configuration_item.get('tags', [])}
    if tags.get('Config') != 'True':
        return {
            'compliance_type': 'NOT_APPLICABLE',
            'annotation': 'Instance does not have Config=True tag.'
        }
    
    # 2. Check platform (Windows/Linux)
    platform = configuration_item.get('platform', 'Linux').lower()  # Default to Linux if missing
    if platform != 'windows':
        return {
            'compliance_type': 'NOT_APPLICABLE',
            'annotation': 'Not a Windows instance.'
        }

    # 3. Fetch alarms
    alarms = cloudwatch.describe_alarms(AlarmTypes=['MetricAlarm'])['MetricAlarms']
    
    required_memory_alarm = False
    required_disk_alarms = {'C:': False, 'D:': False, 'E:': False}
    
    for alarm in alarms:
        metrics = alarm.get('Metrics', [])
        if not metrics and alarm.get('MetricName'):
            metrics = [{'MetricStat': {'Metric': {'MetricName': alarm['MetricName'], 'Dimensions': alarm['Dimensions']}}}]
        
        for m in metrics:
            metric = m['MetricStat']['Metric']
            metric_name = metric['MetricName']
            dimensions = {d['Name']: d['Value'] for d in metric['Dimensions']}
            
            if dimensions.get('InstanceId') == instance_id:
                if metric_name == 'Memory Available Bytes':
                    required_memory_alarm = True
                if metric_name == 'LogicalDisk % Free Space' and dimensions.get('LogicalDiskName') in required_disk_alarms:
                    required_disk_alarms[dimensions['LogicalDiskName']] = True

    # 4. Final compliance check
    if required_memory_alarm and all(required_disk_alarms.values()):
        compliance_type = 'COMPLIANT'
        annotation = 'All required alarms exist.'
    else:
        compliance_type = 'NON_COMPLIANT'
        annotation = 'Missing Memory or Disk alarms (C:, D:, E:).'

    # 5. Send evaluation back
    response = config.put_evaluations(
        Evaluations=[
            {
                'ComplianceResourceType': configuration_item['resourceType'],
                'ComplianceResourceId': instance_id,
                'ComplianceType': compliance_type,
                'Annotation': annotation,
                'OrderingTimestamp': configuration_item['configurationItemCaptureTime']
            },
        ],
        ResultToken=event['resultToken']
    )
    
    return response
