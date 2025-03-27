import boto3
import time

ssm = boto3.client('ssm')
ec2 = boto3.client('ec2')

def lambda_handler(event, context):
    instance_id = event.get('InstanceId')
    if not instance_id:
        return {"status": "error", "message": "InstanceId not provided in the event"}

    # Get OS platform info
    reservations = ec2.describe_instances(InstanceIds=[instance_id])['Reservations']
    if not reservations:
        return {"status": "error", "message": "Instance not found"}

    platform = reservations[0]['Instances'][0].get('Platform', 'Linux')  # 'Windows' if Windows, else Linux
    print(f"Detected platform: {platform}")

    if platform.lower() == 'windows':
        check_cmd = 'Get-Service AmazonSSMAgent | Select-Object -ExpandProperty Status'
        restart_cmd = 'Restart-Service AmazonSSMAgent'
    else:
        check_cmd = 'sudo systemctl is-active amazon-ssm-agent || echo "inactive"'
        restart_cmd = 'sudo systemctl restart amazon-ssm-agent'

    # 1. Run command to check SSM Agent status
    check_response = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunPowerShellScript" if platform.lower() == 'windows' else "AWS-RunShellScript",
        Parameters={'commands': [check_cmd]},
        TimeoutSeconds=30
    )

    command_id = check_response['Command']['CommandId']
    time.sleep(2)  # Wait before fetching the result

    output = ssm.get_command_invocation(
        CommandId=command_id,
        InstanceId=instance_id
    )

    status_output = output.get('StandardOutputContent', '').strip().lower()
    print(f"SSM Agent status: {status_output}")

    # 2. If not running, restart
    if 'running' not in status_output and 'active' not in status_output:
        print("SSM Agent is NOT running. Attempting to restart...")

        restart_response = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunPowerShellScript" if platform.lower() == 'windows' else "AWS-RunShellScript",
            Parameters={'commands': [restart_cmd]},
            TimeoutSeconds=30
        )

        return {
            "status": "restarted",
            "instance_id": instance_id,
            "platform": platform,
            "restart_command_id": restart_response['Command']['CommandId']
        }
    else:
        print("SSM Agent is already running.")
        return {
            "status": "running",
            "instance_id": instance_id,
            "platform": platform
        }
