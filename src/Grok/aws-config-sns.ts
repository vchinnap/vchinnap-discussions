import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { aws_config as config } from 'aws-cdk-lib';

export class EbsBackupPlanRule extends cdk.Stack {
    constructor(scope: Construct, id: string, props?: cdk.StackProps) {
        super(scope, id, props);

        // Define key variables (e.g., from context or environment)
        const accountID = this.node.tryGetContext('accountID');
        const region = process.env.TargetAccountRegion || 'us-east-1';
        const ruleName = 'hcops-ec2-volume-in-use-check';
        const sourceIdentifier = 'EBS_IN_BACKUP_PLAN'; // AWS managed rule
        const snsTopicArn = `arn:aws:sns:${region}:${accountID}:HC-PATCH-SBX-TOPIC`;
        const automationAssumeRole = `arn:aws:iam::${accountID}:role/HC-AWS-AutomationRole`;

        // Name of the manually created SSM document
        const ssmDocumentName = 'CustomConfigNotification';

        // Parameters expected by the SSM document
        const parameters = {
            AutomationAssumeRole: { StaticValue: { Values: [automationAssumeRole] } },
            TopicArn: { StaticValue: { Values: [snsTopicArn] } },
            resourceId: { ResourceValue: { Value: 'RESOURCE_ID' } },
            resourceType: { ResourceValue: { Value: 'RESOURCE_TYPE' } },
            complianceType: { ResourceValue: { Value: 'COMPLIANCE_TYPE' } },
            accountId: { ResourceValue: { Value: 'AWS_ACCOUNT_ID' } },
            awsRegion: { ResourceValue: { Value: 'AWS_REGION' } },
            configRuleName: { ResourceValue: { Value: 'CONFIG_RULE_NAME' } },
            annotation: { ResourceValue: { Value: 'ANNOTATION' } },
        };

        // Define the AWS Config Rule
        const rule = new config.CfnConfigRule(this, 'EbsBackupRule', {
            configRuleName: ruleName,
            source: {
                owner: 'AWS',
                sourceIdentifier: sourceIdentifier,
            },
            description: 'Checks whether EBS volumes are backed up as per backup policy.',
        });

        // Define the remediation configuration referencing the manual SSM document
        const remediationRule = new config.CfnRemediationConfiguration(this, `${ruleName}-Remediation`, {
            configRuleName: ruleName,
            targetId: ssmDocumentName, // Reference the manually created document
            targetType: 'SSM_DOCUMENT',
            automatic: true,
            executionControls: {
                ssmControls: {
                    concurrentExecutionRatePercentage: 50,
                    errorPercentage: 10,
                },
            },
            maximumAutomaticAttempts: 3,
            parameters: parameters,
            resourceType: 'AWS::EC2::Volume',
            retryAttemptSeconds: 300,
            targetVersion: '1', // Specify the version if needed
        });

        // Ensure remediation depends on the Config rule
        remediationRule.node.addDependency(rule);
    }
}
