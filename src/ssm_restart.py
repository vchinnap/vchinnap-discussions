import boto3
import time

ssm = boto3.client('ssm')
ec2 = boto3.client('ec2')

def lambda_handler(event, context):
    instance_id = event.get('InstanceId')
    if not instance_id:
        return {"status": "error", "message": "InstanceId not provided in the event"}

    # 1. Get platform info
    try:
        reservations = ec2.describe_instances(InstanceIds=[instance_id])['Reservations']
        instance = reservations[0]['Instances'][0]
        platform = instance.get('Platform', 'Linux')
        is_windows = platform.lower() == 'windows'
    except Exception as e:
        return {"status": "error", "message": f"Failed to get instance platform: {str(e)}"}

    if not is_windows:
        return {"status": "unsupported", "message": "This solution only supports Windows EC2 instances."}

    # 2. Check if SSM Agent is running
    try:
        check_cmd = 'Get-Service AmazonSSMAgent | Select-Object -ExpandProperty Status'
        check_response = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunPowerShellScript",
            Parameters={'commands': [check_cmd]},
            TimeoutSeconds=30
        )

        command_id = check_response['Command']['CommandId']
        time.sleep(3)

        result = ssm.get_command_invocation(CommandId=command_id, InstanceId=instance_id)
        status_output = result.get('StandardOutputContent', '').strip().lower()
        command_status = result.get('Status')

        if command_status in ['DeliveryTimedOut', 'Undeliverable']:
            return {
                "status": "unreachable",
                "message": "SSM Agent is down. Cannot send command.",
                "command_status": command_status
            }

        if 'running' in status_output:
            return {
                "status": "running",
                "message": "SSM Agent is already running. No action needed.",
                "instance_id": instance_id
            }
    except Exception as e:
        return {"status": "error", "message": f"Failed to check SSM Agent status: {str(e)}"}

    # 3. Agent is stopped – invoke the pre-created PowerShell script to restart it
    try:
        invoke_script = [
            'powershell.exe -ExecutionPolicy Bypass -File "C:\\Scripts\\AutoStart-SSMAgent.ps1"'
        ]

        restart_response = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunPowerShellScript",
            Parameters={'commands': invoke_script},
            TimeoutSeconds=60
        )

        restart_command_id = restart_response['Command']['CommandId']
        time.sleep(5)

        result = ssm.get_command_invocation(CommandId=restart_command_id, InstanceId=instance_id)

        if result['Status'] == 'Success':
            return {
                "status": "invoked_restart_script",
                "message": "Restart script executed successfully.",
                "instance_id": instance_id,
                "stdout": result.get('StandardOutputContent', ''),
                "stderr": result.get('StandardErrorContent', '')
            }
        else:
            return {
                "status": "invoke_failed",
                "message": "Failed to execute restart script.",
                "stdout": result.get('StandardOutputContent', ''),
                "stderr": result.get('StandardErrorContent', ''),
                "command_status": result['Status']
            }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Error invoking restart script: {str(e)}",
            "instance_id": instance_id
        }
