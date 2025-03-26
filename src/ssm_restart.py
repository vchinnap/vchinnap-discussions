#!/usr/bin/env python3

import subprocess
import time
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def is_ssm_agent_running():
    try:
        status = subprocess.check_output(["systemctl", "is-active", "amazon-ssm-agent"])
        return status.strip() == b"active"
    except subprocess.CalledProcessError:
        return False

def restart_ssm_agent():
    try:
        subprocess.run(["sudo", "systemctl", "restart", "amazon-ssm-agent"], check=True)
        logging.info("SSM Agent restart command issued.")
        time.sleep(2)
        if is_ssm_agent_running():
            logging.info("SSM Agent restarted and is now running.")
            return {"status": "restarted"}
        else:
            logging.error("SSM Agent did not restart successfully.")
            return {"status": "restart_failed"}
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to restart SSM Agent: {e}")
        return {"status": "error", "details": str(e)}

def handler():
    if not is_ssm_agent_running():
        logging.warning("SSM Agent is not running. Attempting restart...")
        return restart_ssm_agent()
    else:
        logging.info("SSM Agent is running.")
        return {"status": "running"}
