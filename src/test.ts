import * as cdk from 'aws-cdk-lib';
import * as config from 'aws-cdk-lib/aws-config';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

export class AwsConfigRemediationStack extends cdk.Stack {
    constructor(scope: Construct, id: string, props?: cdk.StackProps) {
        super(scope, id, props);

        // Create an IAM role for remediation
        const remediationRole = new iam.Role(this, 'RemediationRole', {
            assumedBy: new iam.ServicePrincipal('ssm.amazonaws.com'),
            managedPolicies: [
                iam.ManagedPolicy.fromAwsManagedPolicyName("service-role/AWSConfigRemediationPolicy")
            ]
        });

        // AWS Config Rule Name
        const configRuleName = "YourConfigRule";

        // Define the AWS Config Remediation
        new config.CfnRemediationConfiguration(this, 'ConfigRemediation', {
            configRuleName: configRuleName,
            targetType: "SSM_DOCUMENT",
            targetId: "AWS-PublishSNSNotification",
            automatic: true,  // Enables auto-remediation
            maximumAutomaticAttempts: 3,
            retryAttemptSeconds: 30,
            parameters: {
                "AutomationAssumeRole": {
                    staticValue: { values: [remediationRole.roleArn] }
                },
                "Message": {
                    staticValue: { values: ["Testing HCOPS AWS Config 1111"] }
                },
                "TopicArn": {
                    staticValue: { values: ["arn:aws:sns:us-east-1:123456789012:YourSNSTopic"] }
                }
            }
        });
    }
}

// Create the app and deploy the stack
const app = new cdk.App();
new AwsConfigRemediationStack(app, 'AwsConfigRemediationStack');




import { App, TerraformStack } from 'cdktf';
import { AzurermProvider, ResourceGroup, VirtualMachine } from '@cdktf/provider-azurerm';
import { TerraformOutput } from 'cdktf';

class AzureVmControlStack extends TerraformStack {
  constructor(scope: App, id: string) {
    super(scope, id);

    // Azure Provider (you might need to configure this based on your needs)
    new AzurermProvider(this, 'Azure', {
      features: {},
    });

    // Reference an existing Resource Group
    const resourceGroupName = 'your-resource-group-name'; 
    const resourceGroup = ResourceGroup.get(this, 'ExistingResourceGroup', {
      name: resourceGroupName,
    });

    // Reference an existing Virtual Machine
    const vmName = 'your-vm-name'; 
    const existingVm = VirtualMachine.get(this, 'ExistingVirtualMachine', {
      name: vmName,
      resourceGroupName: resourceGroupName,
    });

    // Define Terraform outputs for start/stop commands
    new TerraformOutput(this, 'vmStartCommand', {
      value: `az vm start --resource-group ${resourceGroupName} --name ${vmName}`,
    });

    new TerraformOutput(this, 'vmStopCommand', {
      value: `az vm stop --resource-group ${resourceGroupName} --name ${vmName}`,
    });
  }
}

const app = new App();
new AzureVmControlStack(app, 'azure-vm-control');
app.synth();















import * as cdk from 'aws-cdk-lib';
import { BBBBAWSConfigRuleConstruct } from '@bbbb-cdk/aws-config';
import { Construct } from 'constructs';
import * as config from 'aws-cdk-lib/aws-config';

export class EbsOptimizedInstanceRule extends cdk.Stack {
    constructor(scope: Construct, id: string, props?: cdk.StackProps) {
        super(scope, id, props);

        // AWS Config Rule
        const configRule = new BBBBAWSConfigRuleConstruct(this, 'aws-config-rule', {
            source: {
                owner: 'AWS',
                sourceIdentifier: 'EBS_OPTIMIZED_INSTANCE',
            },
            configRuleName: 'hwss-ebs-optimized-instance',
            description: 'Checks if Amazon EBS optimization is enabled for EC2 instances.',
        });

        // Dummy Remediation using SNS Notification
        new config.CfnRemediationConfiguration(this, 'EbsOptimizationSNSRemediation', {
            configRuleName: configRule.configRuleName,  // Attach to the existing rule
            targetId: "arn:aws:sns:<REGION>:<ACCOUNT_ID>:TestRemediationSNS", // SNS Topic
            targetType: "SNS",
            parameters: {
                "Message": {
                    StaticValue: {
                        Values: ["AWS Config detected non-compliance: EBS optimization is not enabled."]
                    }
                },
                "TopicArn": {
                    StaticValue: {
                        Values: ["arn:aws:sns:<REGION>:<ACCOUNT_ID>:TestRemediationSNS"]
                    }
                }
            },
            automatic: true // Automatically trigger SNS when non-compliant
        });
    }
}







import * as cdk from 'aws-cdk-lib';
import * as config from 'aws-cdk-lib/aws-config';

const stack = new cdk.Stack();

const accountId = cdk.Aws.ACCOUNT_ID; // ✅ Dynamically retrieves AWS Account ID
const awsRegion = cdk.Aws.REGION; // ✅ Dynamically retrieves AWS Region
const configRuleName = "EBS_BACKUP_PLAN_RULE"; // Ensure this rule exists in AWS Config
const complianceType = "NON_COMPLIANT";
const resourceType = "AWS::EC2::Volume";

// ✅ Create a detailed annotation message with dynamic values
const annotationMessage = `Remediation triggered:
- AWS Account ID: ${accountId}
- AWS Region: ${awsRegion}
- Config Rule Name: ${configRuleName}
- Compliance Type: ${complianceType}
- Resource Type: ${resourceType}
- Action: EBS volume is not backed up, applying remediation`;

const remediation = new config.CfnRemediationConfiguration(stack, 'MyRemediation', {
  configRuleName: configRuleName,
  targetId: "AWS-EnableEBSBackups", // AWS managed SSM Automation Document
  targetType: "SSM_DOCUMENT",
  parameters: {
    // ✅ Annotation now contains dynamically fetched values
    "annotation": { StaticValue: { Values: [annotationMessage] } },

    // ✅ Allowed: resourceId as ResourceValue (dynamically retrieved from the event)
    "resourceId": { ResourceValue: { Value: "RESOURCE_ID" } },

    // ✅ These are now dynamically retrieved instead of hardcoded
    "accountId": { StaticValue: { Values: [accountId] } }, 
    "awsRegion": { StaticValue: { Values: [awsRegion] } },
    "configRuleName": { StaticValue: { Values: [configRuleName] } },
    "complianceType": { StaticValue: { Values: [complianceType] } },
    "resourceType": { StaticValue: { Values: [resourceType] } }
  }
});













import * as cdk from 'aws-cdk-lib';
import * as config from 'aws-cdk-lib/aws-config';

const stack = new cdk.Stack();

const accountId = cdk.Aws.ACCOUNT_ID; // ✅ Dynamically retrieves AWS Account ID
const awsRegion = cdk.Aws.REGION; // ✅ Dynamically retrieves AWS Region
const configRuleName = "EBS_BACKUP_PLAN_RULE"; // Ensure this rule exists in AWS Config
const complianceType = "NON_COMPLIANT";
const resourceType = "AWS::EC2::Volume";

// ✅ Keep annotation concise without redundant fields
const annotationMessage = `Remediation triggered for ${configRuleName} in ${awsRegion}. 
Applying fix for a non-compliant ${resourceType}. Check AWS Config for details.`;

const remediation = new config.CfnRemediationConfiguration(stack, 'MyRemediation', {
  configRuleName: configRuleName,
  targetId: "AWS-EnableEBSBackups", // AWS managed SSM Automation Document
  targetType: "SSM_DOCUMENT",
  parameters: {
    // ✅ Annotation now contains only essential information
    "annotation": { StaticValue: { Values: [annotationMessage] } },

    // ✅ Required structured inputs (MUST BE PASSED separately)
    "resourceId": { ResourceValue: { Value: "RESOURCE_ID" } }, // Dynamic

    // ❌ Must be static because AWS Config requires them in a structured format
    "accountId": { StaticValue: { Values: [accountId] } }, 
    "awsRegion": { StaticValue: { Values: [awsRegion] } },
    "configRuleName": { StaticValue: { Values: [configRuleName] } },
    "complianceType": { StaticValue: { Values: [complianceType] } },
    "resourceType": { StaticValue: { Values: [resourceType] } }
  }
});






const resourceId = {
  "Message": { ResourceValue: { Value: "RESOURCE_ID" } }
};

const parameters = {
  "AutomationAssumeRole": { StaticValue: { Values: [automationAssumeRole] } },
  "TopicArn": { StaticValue: { Values: [snsTopicArn] } },
  "Message": { ResourceValue: { Value: "RESOURCE_ID" } },
  "Subject": { 
    StaticValue: { 
      Values: [`AWS Config Violation: ${ruleName} | ${complianceType} | in ${region} for ${resourceType} [${resourceId.Message.ResourceValue.Value}]`] 
    } 
  },
  "accountId": { StaticValue: { Values: [accountID] } },
  "awsRegion": { StaticValue: { Values: [region] } },
  "configRuleName": { StaticValue: { Values: [ruleName] } },
  "complianceType": { StaticValue: { Values: [complianceType] } },
};
