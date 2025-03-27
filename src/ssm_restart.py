import boto3
import time

ssm = boto3.client('ssm')
ec2 = boto3.client('ec2')

def lambda_handler(event, context):
    instance_id = event.get('InstanceId')
    if not instance_id:
        return {"status": "error", "message": "InstanceId not provided in the event"}

    # 1. Get platform (Windows or Linux)
    try:
        reservations = ec2.describe_instances(InstanceIds=[instance_id])['Reservations']
        if not reservations:
            return {"status": "error", "message": "Instance not found"}

        instance = reservations[0]['Instances'][0]
        platform = instance.get('Platform', 'Linux')  # 'Windows' or default to 'Linux'
        is_windows = platform.lower() == 'windows'

        print(f"Detected platform: {platform}")
    except Exception as e:
        return {"status": "error", "message": f"Error fetching instance platform: {str(e)}"}

    # 2. Set commands based on platform
    if is_windows:
        check_cmd = 'Get-Service AmazonSSMAgent | Select-Object -ExpandProperty Status'
        restart_cmd = 'Restart-Service AmazonSSMAgent'
        document = 'AWS-RunPowerShellScript'
    else:
        check_cmd = 'sudo systemctl is-active amazon-ssm-agent || echo "inactive"'
        restart_cmd = 'sudo systemctl restart amazon-ssm-agent'
        document = 'AWS-RunShellScript'

    try:
        # 3. Send command to check agent status
        check_response = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName=document,
            Parameters={'commands': [check_cmd]},
            TimeoutSeconds=30
        )

        command_id = check_response['Command']['CommandId']
        time.sleep(3)

        # 4. Get command output
        invocation = ssm.get_command_invocation(
            CommandId=command_id,
            InstanceId=instance_id
        )

        status_output = invocation.get('StandardOutputContent', '').strip().lower()
        command_status = invocation.get('Status')

        print(f"Command status: {command_status}")
        print(f"SSM Agent status output: {status_output}")

        if command_status in ['DeliveryTimedOut', 'Undeliverable', 'Terminated']:
            return {
                "status": "unreachable",
                "message": f"Cannot connect to SSM Agent on {instance_id}. It may be stopped.",
                "command_status": command_status
            }

        # 5. Restart if not running
        if 'running' not in status_output and 'active' not in status_output:
            print("SSM Agent is not active. Attempting restart...")
            restart_response = ssm.send_command(
                InstanceIds=[instance_id],
                DocumentName=document,
                Parameters={'commands': [restart_cmd]},
                TimeoutSeconds=30
            )

            return {
                "status": "restarted",
                "platform": platform,
                "instance_id": instance_id,
                "restart_command_id": restart_response['Command']['CommandId']
            }
        else:
            return {
                "status": "running",
                "platform": platform,
                "instance_id": instance_id
            }

    except ssm.exceptions.InvalidInstanceId as e:
        return {"status": "error", "message": f"Invalid instance ID: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}
