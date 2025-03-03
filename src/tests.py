import boto3
import time

# Initialize AWS Config client
client = boto3.client('config')

def wait_for_remediation_completion(config_rule_name):
    """Waits for ongoing remediation execution to complete."""
    print(f"Checking remediation execution status for: {config_rule_name}")

    while True:
        try:
            response = client.describe_remediation_execution_status(
                ConfigRuleName=config_rule_name
            )

            if "RemediationExecutionStatuses" not in response or not response["RemediationExecutionStatuses"]:
                print("No active remediation found.")
                return

            # Check if any resource is still in progress
            in_progress = any(
                status["RemediationExecutionStepStatuses"][0]["StepStatus"] == "IN_PROGRESS"
                for status in response["RemediationExecutionStatuses"]
                if "RemediationExecutionStepStatuses" in status and status["RemediationExecutionStepStatuses"]
            )

            if not in_progress:
                print("Remediation execution completed.")
                return

            print("Remediation is still in progress... waiting 10 seconds.")
            time.sleep(10)

        except client.exceptions.NoSuchRemediationConfigurationException:
            print("No remediation found for this rule.")
            return
        except Exception as e:
            print(f"Error checking remediation status: {str(e)}")
            return

def delete_remediation_configuration(config_rule_name):
    """Deletes remediation configuration for the given config rule."""
    try:
        response = client.delete_remediation_configuration(
            ConfigRuleName=config_rule_name
        )
        print(f"Successfully deleted remediation configuration for: {config_rule_name}")
    except client.exceptions.NoSuchRemediationConfigurationException:
        print(f"Remediation configuration not found for: {config_rule_name}")
    except Exception as e:
        print(f"Error deleting remediation configuration: {str(e)}")

def delete_config_rule(config_rule_name):
    """Deletes the AWS Config rule."""
    try:
        response = client.delete_config_rule(
            ConfigRuleName=config_rule_name
        )
        print(f"Successfully deleted config rule: {config_rule_name}")
    except client.exceptions.NoSuchConfigRuleException:
        print(f"Config rule not found: {config_rule_name}")
    except Exception as e:
        print(f"Error deleting config rule: {str(e)}")

if __name__ == "__main__":
    config_rule_name = "your-config-rule-name"  # Change this to your actual Config Rule name

    # Step 1: Wait for remediation execution to complete
    wait_for_remediation_completion(config_rule_name)

    # Step 2: Delete remediation configuration
    delete_remediation_configuration(config_rule_name)

    # Step 3: Delete the config rule
    delete_config_rule(config_rule_name)
