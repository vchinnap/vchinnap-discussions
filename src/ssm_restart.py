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
                "message": "SSM Agent is down. Cannot deploy script.",
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

    # 3. SSM Agent is not running — deploy self-healing script + scheduled task
    try:
        create_script_and_task = [
            # Ensure folder exists
            'New-Item -ItemType Directory -Path "C:\\Scripts" -Force',

            # Create restart script
            '$script = @\'',
            '$service = Get-Service AmazonSSMAgent -ErrorAction SilentlyContinue',
            'if ($service.Status -ne "Running") {',
            '    Start-Service AmazonSSMAgent',
            '    "Restarted at $(Get-Date)" | Out-File "C:\\Scripts\\ssm-restart-log.txt" -Append',
            '}',
            '\'@',
            '$script | Set-Content -Path "C:\\Scripts\\AutoStart-SSMAgent.ps1"',

            # Register scheduled task
            '$action = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-NoProfile -WindowStyle Hidden -File C:\\Scripts\\AutoStart-SSMAgent.ps1"',
            '$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 2) -RepetitionDuration ([TimeSpan]::MaxValue)',
            '$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest',
            'Register-ScheduledTask -TaskName "AutoStartSSMAgent" -Action $action -Trigger $trigger -Principal $principal -Force'
        ]

        setup_response = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunPowerShellScript",
            Parameters={'commands': create_script_and_task},
            TimeoutSeconds=60
        )

        setup_command_id = setup_response['Command']['CommandId']
        time.sleep(5)

        setup_result = ssm.get_command_invocation(
            CommandId=setup_command_id,
            InstanceId=instance_id
        )

        if setup_result['Status'] == 'Success':
            return {
                "status": "task_created",
                "message": "Auto-restart script and scheduled task successfully deployed.",
                "instance_id": instance_id
            }
        else:
            return {
                "status": "setup_failed",
                "message": "Failed to create restart task.",
                "stdout": setup_result.get('StandardOutputContent', ''),
                "stderr": setup_result.get('StandardErrorContent', ''),
                "instance_id": instance_id
            }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Error while deploying scheduled task: {str(e)}",
            "instance_id": instance_id
        }
