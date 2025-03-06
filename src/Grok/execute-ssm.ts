import * as cdk from 'aws-cdk-lib';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import { Construct } from 'constructs';

export class SSMExecutionStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Reference an existing IAM role ARN (replace with your role ARN)
    const automationRoleArn = 'arn:aws:iam::ACCOUNT_ID:role/YourExistingAutomationRole'; // Update this

    // Execute the existing Automation document
    const automationExecution = new ssm.CfnAutomationExecution(this, 'ExecuteAutomation', {
      documentName: 'Your-Existing-Document-Name', // Replace with your document name
      parameters: {
        AutomationAssumeRole: [automationRoleArn]
        // Add your document's required parameters here
      },
      mode: 'Auto',
      maxConcurrency: '1',
      maxErrors: '1'
    });

    // Output the execution ID
    new cdk.CfnOutput(this, 'ExecutionId', {
      value: automationExecution.ref,
      description: 'SSM Automation Execution ID'
    });
  }
}

// App setup
const app = new cdk.App();
new SSMExecutionStack(app, 'SSMExecutionStack');
