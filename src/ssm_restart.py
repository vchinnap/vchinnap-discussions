import boto3
import time

ssm = boto3.client('ssm')

def lambda_handler(event, context):
    instance_id = event.get('InstanceId')
    if not instance_id:
        return {"status": "error", "message": "InstanceId not provided in the event"}

    print(f"Checking SSM Agent status on instance: {instance_id}")

    # 1. Run command to check SSM Agent status
    check_command = "sudo systemctl is-active amazon-ssm-agent || echo 'inactive'"
    check_response = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={'commands': [check_command]},
        TimeoutSeconds=30
    )

    command_id = check_response['Command']['CommandId']
    
    # Wait briefly before getting the result
    time.sleep(2)

    # 2. Get command output
    output = ssm.get_command_invocation(
        CommandId=command_id,
        InstanceId=instance_id
    )

    status_output = output.get('StandardOutputContent', '').strip()
    print(f"SSM Agent status output: {status_output}")

    # 3. Restart if not active
    if status_output != 'active':
        print("SSM Agent is not active. Attempting to restart...")
        restart_response = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunShellScript",
            Parameters={'commands': ['sudo systemctl restart amazon-ssm-agent']},
            TimeoutSeconds=30
        )
        return {
            "status": "restarted",
            "instance_id": instance_id,
            "restart_command_id": restart_response['Command']['CommandId']
        }
    else:
        print("SSM Agent is already active.")
        return {
            "status": "active",
            "instance_id": instance_id
        }
