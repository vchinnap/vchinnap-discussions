import boto3
import time

ssm = boto3.client('ssm')
ec2 = boto3.client('ec2')

def lambda_handler(event, context):
    instance_id = event.get('InstanceId')
    if not instance_id:
        return {"status": "error", "message": "InstanceId not provided in the event"}

    # 1. Get platform info (Windows or Linux)
    try:
        reservations = ec2.describe_instances(InstanceIds=[instance_id])['Reservations']
        if not reservations:
            return {"status": "error", "message": "Instance not found"}

        instance = reservations[0]['Instances'][0]
        platform = instance.get('Platform', 'Linux')  # 'Windows' or assume 'Linux'
        is_windows = platform.lower() == 'windows'
        print(f"Detected platform: {platform}")
    except Exception as e:
        return {"status": "error", "message": f"Error getting platform info: {str(e)}"}

    # 2. Set up commands based on platform
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

        check_command_id = check_response['Command']['CommandId']
        time.sleep(3)

        check_result = ssm.get_command_invocation(
            CommandId=check_command_id,
            InstanceId=instance_id
        )

        check_status = check_result.get('Status')
        check_stdout = check_result.get('StandardOutputContent', '').strip().lower()
        check_stderr = check_result.get('StandardErrorContent', '').strip()

        print(f"Check SSM Agent status: {check_status}")
        print(f"STDOUT: {check_stdout}")
        print(f"STDERR: {check_stderr}")

        if check_status in ['DeliveryTimedOut', 'Undeliverable', 'Terminated']:
            return {
                "status": "unreachable",
                "message": f"Cannot connect to SSM Agent on {instance_id}. It may be stopped.",
                "check_status": check_status,
                "stdout": check_stdout,
                "stderr": check_stderr
            }

        # 4. Restart if not active/running
        if 'running' not in check_stdout and 'active' not in check_stdout:
            print("SSM Agent not running. Sending restart command...")

            restart_response = ssm.send_command(
                InstanceIds=[instance_id],
                DocumentName=document,
                Parameters={'commands': [restart_cmd]},
                TimeoutSeconds=30
            )

            restart_command_id = restart_response['Command']['CommandId']
            time.sleep(3)

            try:
                restart_result = ssm.get_command_invocation(
                    CommandId=restart_command_id,
                    InstanceId=instance_id
                )

                restart_status = restart_result.get('Status')
                restart_stdout = restart_result.get('StandardOutputContent', '').strip()
                restart_stderr = restart_result.get('StandardErrorContent', '').strip()

                print(f"Restart command status: {restart_status}")
                print(f"STDOUT: {restart_stdout}")
                print(f"STDERR: {restart_stderr}")

                if restart_status == 'Success':
                    return {
                        "status": "restart_succeeded",
                        "platform": platform,
                        "instance_id": instance_id,
                        "restart_command_id": restart_command_id,
                        "output": restart_stdout
                    }
                else:
                    return {
                        "status": "restart_failed",
                        "platform": platform,
                        "instance_id": instance_id,
                        "restart_command_id": restart_command_id,
                        "restart_status": restart_status,
                        "stdout": restart_stdout,
                        "stderr": restart_stderr
                    }

            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Could not get restart command result: {str(e)}",
                    "restart_command_id": restart_command_id
                }

        else:
            return {
                "status": "running",
                "platform": platform,
                "instance_id": instance_id,
                "output": check_stdout
            }

    except ssm.exceptions.InvalidInstanceId as e:
        return {"status": "error", "message": f"Invalid instance ID: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}
