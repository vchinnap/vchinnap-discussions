import * as cdk from 'aws-cdk-lib';
import { BMAWSConfigRuleConstruct } from '@bmo-cdk/aws-config';
import { Construct } from 'constructs';
import { aws_config as config } from 'aws-cdk-lib';

export class EbsBackupPlanRule extends cdk.Stack {
    constructor(scope: cdk.Construct, id: string, props?: cdk.StackProps) {
        super(scope, id, props);

        // Retrieve values from CDK context or environment variables
        var stage = this.node.tryGetContext('Stage');
        var accountID = this.node.tryGetContext('accountID');
        var stageShortCode = this.node.tryGetContext('stageShortCode');
        var regionShortCode = this.node.tryGetContext('regionShortCode');
        var region = process.env.TargetAccountRegion;

        // Define Config Rule Name
        const ruleName = 'hcops-ec2-volume-in-use-check';

        // AWS Managed Rule for EBS Backup Plan Validation
        const sourceIdentifier = 'EBS_IN_BACKUP_PLAN';

        // Define SSM Document Name for automation
        const ssmDocumentName = 'AWS-PublishSNSNotification';

        // Define SNS Topic for notifications
        const snsTopicArn = `arn:aws:sns:${region}:${accountID}:HC-PATCH-SBX-TOPIC`;

        // Define IAM Role for SSM Automation Execution
        const automationAssumeRole = `arn:aws:iam::${accountID}:role/HC-AWS-AutomationRole`;

        // ✅ Message format for AWS Config remediation notifications
        const message = `AWS Config non-compliant resource.
ResourceId: {resourceId}
ResourceType: {resourceType}
ComplianceType: {complianceType}
AWS Account ID: {accountId}
AWS Region: {awsRegion}
Config Rule Name: {configRuleName}
Details: {annotation}`;

        // Define parameters for the SSM Automation document
        const parameters = {
            "AutomationAssumeRole": { StaticValue: { Values: [automationAssumeRole] } },
            "TopicArn": { StaticValue: { Values: [snsTopicArn] } },
            "Message": { StaticValue: { Values: [message] } }
        };

        // ✅ Define AWS Config Rule (EBS Backup Plan Check)
        const rule = new BMAWSConfigRuleConstruct(this, ruleName, {
            configRuleName: ruleName,
            source: {
                owner: 'AWS',
                sourceIdentifier: sourceIdentifier, // ✅ Uses AWS Managed Rule for validation
            },
            description: 'Checks whether EBS volumes are backed up as per backup policy.'
        });

        // ✅ Create Remediation Configuration for non-compliant resources
        const remediationRule = new config.CfnRemediationConfiguration(this, ruleName + '-Remediation', {
            configRuleName: rule.configRuleName,
            targetId: ssmDocumentName, // ✅ Calls SSM Automation document
            targetType: 'SSM_DOCUMENT',
            automatic: true,
            executionControls: {
                ssmControls: {
                    concurrentExecutionRatePercentage: 50,
                    errorPercentage: 10,
                },
            },
            maximumAutomaticAttempts: 3, // ✅ Retries if needed
            parameters: parameters, // ✅ Passes required parameters
            resourceType: 'AWS::EC2::Volume', // ✅ Targets EBS Volumes
            retryAttemptSeconds: 300,
            targetVersion: '1',
        });

        // ✅ Ensures remediation executes after Config rule creation
        remediationRule.node.addDependency(rule);
    }
}
