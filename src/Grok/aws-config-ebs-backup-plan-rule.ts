import * as cdk from 'aws-cdk-lib';
import { BMAWSConfigRuleConstruct } from '@bmo-cdk/aws-config';
import { Construct } from 'constructs';
import { aws_config as config } from 'aws-cdk-lib';

export class EbsBackupPlanRule extends cdk.Stack {
    constructor(scope: cdk.Construct, id: string, props?: cdk.StackProps) {
        super(scope, id, props);

        var stage = this.node.tryGetContext('Stage') ?? 'default-stage';
        var accountID = this.node.tryGetContext('accountID') ?? process.env.CDK_DEFAULT_ACCOUNT;
        var stageShortCode = this.node.tryGetContext('stageShortCode') ?? 'default-shortcode';
        var regionShortCode = this.node.tryGetContext('regionShortCode') ?? 'default-region';
        var region = process.env.TargetAccountRegion ?? process.env.CDK_DEFAULT_REGION;

        // Define Config Rule Name
        const ruleName = 'hcops-ec2-volume-in-use-check';

        // Keeping EBS_IN_BACKUP_PLAN as requested
        const sourceIdentifier = 'EBS_IN_BACKUP_PLAN';

        // Define SSM Document Name
        const ssmDocumentName = 'AWS-PublishSNSNotification';

        // Define SNS Topic
        const snsTopicArn = `arn:aws:sns:${region}:${accountID}:HC-PATCH-SBX-TOPIC`;

        // Define Automation Role
        const automationAssumeRole = `arn:aws:iam::${accountID}:role/HC-AWS-AutomationRole`;

        // ✅ Corrected Message Format
        const message = `AWS Config non-compliant resource.
ResourceId: {{RESOURCE_ID}}
ResourceType: {{RESOURCE_TYPE}}
ComplianceType: {{COMPLIANCE_TYPE}}
AWS Account ID: {{ACCOUNT_ID}}
AWS Region: {{AWS_REGION}}
Config Rule Name: {{CONFIG_RULE_NAME}}
Details: {{ANNOTATION}}`;

        // Define parameters for the SSM Automation document
        const parameters = {
            "AutomationAssumeRole": { StaticValue: { Values: [automationAssumeRole] } },
            "TopicArn": { StaticValue: { Values: [snsTopicArn] } },
            "Message": { StaticValue: { Values: [message] } }
        };

        // Define AWS Config Rule (EBS Backup Plan)
        const rule = new BMAWSConfigRuleConstruct(this, ruleName, {
            configRuleName: ruleName,
            source: {
                owner: 'AWS',
                sourceIdentifier: sourceIdentifier, // ✅ Kept EBS_IN_BACKUP_PLAN
            },
            description: 'Checks whether EBS volumes are backed up as per backup policy.'
        });

        // Create the remediation configuration
        const remediationRule = new config.CfnRemediationConfiguration(this, ruleName + '-Remediation', {
            configRuleName: rule.configRuleName,
            targetId: ssmDocumentName,
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
            resourceType: 'AWS::EC2::Volume', // ✅ Keeping this as EBS volumes relate to backup
            retryAttemptSeconds: 300,
            targetVersion: '1',
        });

        remediationRule.node.addDependency(rule);
    }
}
