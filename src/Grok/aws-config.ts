import * as cdk from '@aws-cdk/core';
import * as config from '@aws-cdk/aws-config';
import * as ssm from '@aws-cdk/aws-ssm';

export class Ec2RemediationStack extends cdk.Stack {
  constructor(scope: cdk.Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Define a Config rule to check for required tags on EC2 instances
    const rule = new config.ManagedRule(this, 'RequiredTagsRule', {
      identifier: 'REQUIRED_TAGS', // AWS managed rule for checking required tags
      configRuleName: 'required-tags',
      inputParameters: {
        tag1Key: 'Environment', // The tag key to enforce
      },
    });

    // Define parameters for the SSM Automation document
    const parameters = {
      InstanceId: {
        resourceValue: {
          value: 'RESOURCE_ID', // AWS Config dynamically replaces this with the non-compliant EC2 instance ID
        },
      },
      TagKey: {
        staticValue: {
          values: ['Environment'], // The key of the tag to add
        },
      },
      TagValue: {
        staticValue: {
          values: ['Production'], // The value of the tag to add
        },
      },
    };

    // Create the remediation configuration
    new config.CfnRemediationConfiguration(this, 'EC2Remediation', {
      configRuleName: rule.configRuleName, // Link to the Config rule
      targetId: 'TagEC2Instance', // Name of the SSM document (replace with your own if different)
      targetType: 'SSM_DOCUMENT', // Specifies that the target is an SSM document
      automatic: true, // Enable automatic remediation
      executionControls: {
        ssmControls: {
          concurrentExecutionRatePercentage: 50, // Limit to 50% concurrent executions
          errorPercentage: 10, // Tolerate up to 10% errors before failing
        },
      },
      maximumAutomaticAttempts: 3, // Retry up to 3 times
      parameters: parameters, // Parameters for the SSM document
      resourceType: 'AWS::EC2::Instance', // Target EC2 instances
      retryAttemptSeconds: 300, // Wait 5 minutes between retries
      targetVersion: '1', // Version of the SSM document
    });
  }
}

// Example usage: Instantiate the stack
const app = new cdk.App();
new Ec2RemediationStack(app, 'Ec2RemediationStack');
