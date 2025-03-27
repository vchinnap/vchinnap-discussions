import subprocess
import time
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def is_ssm_agent_running():
    try:
        status = subprocess.check_output(["systemctl", "is-active", "amazon-ssm-agent"])
        return status.strip() == b"active"
    except subprocess.CalledProcessError:
        return False

def restart_ssm_agent():
    try:
        subprocess.run(["sudo", "systemctl", "restart", "amazon-ssm-agent"], check=True)
        logger.info("SSM Agent restart command issued.")
        time.sleep(2)
        if is_ssm_agent_running():
            logger.info("SSM Agent restarted and is now running.")
            return {"status": "restarted"}
        else:
            logger.error("SSM Agent did not restart successfully.")
            return {"status": "restart_failed"}
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to restart SSM Agent: {e}")
        return {"status": "error", "details": str(e)}

def lambda_handler(event, context):
    instance_id = event.get("InstanceId")

    if not instance_id:
        return {"status": "error", "message": "InstanceId is required in the event"}

    logger.info(f"Processing request for instance: {instance_id}")

    if not is_ssm_agent_running():
        logger.warning("SSM Agent is not running. Attempting restart...")
        result = restart_ssm_agent()
    else:
        logger.info("SSM Agent is running.")
        result = {"status": "running"}

    result["instance_id"] = instance_id
    return result
