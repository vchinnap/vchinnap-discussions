import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { aws_config as config } from 'aws-cdk-lib';

// Define an interface for stack properties
interface EbsBackupPlanProps extends cdk.StackProps {
    accountID?: string; // Optional AWS account ID
    region?: string;    // Optional AWS region
}

/**
 * A CDK stack that creates an AWS Config rule to check if EBS volumes are in a backup plan
 * and sets up automatic remediation to send SNS notifications with full evaluation results
 * for non-compliant volumes.
 */
export class EbsBackupPlanRule extends cdk.Stack {
    // Default region if not provided
    private readonly DEFAULT_REGION = 'us-east-1';
    // Name of the Config rule
    private readonly RULE_NAME = 'hcops-ec2-volume-in-use-check';
    // AWS managed rule identifier for EBS backup plan check
    private readonly SOURCE_IDENTIFIER = 'EBS_IN_BACKUP_PLAN';

    constructor(scope: Construct, id: string, props: EbsBackupPlanProps = {}) {
        super(scope, id, props);

        // Retrieve account ID from props or context, throw error if not found
        const accountID = props.accountID || this.node.tryGetContext('accountID');
        if (!accountID) {
            throw new Error('Account ID must be provided via props or context');
        }

        // Retrieve region from props, environment variable, or default
        const region = props.region || process.env.TargetAccountRegion || this.DEFAULT_REGION;

        // Construct ARNs for SNS topic and automation role
        const snsTopicArn = `arn:aws:sns:${region}:${accountID}:HC-PATCH-SBX-TOPIC`;
        const automationAssumeRole = `arn:aws:iam::${accountID}:role/HC-AWS-AutomationRole`;

        // Create the AWS Config rule to check EBS volumes in backup plan
        const rule = new config.CfnConfigRule(this, 'EbsBackupRule', {
            configRuleName: this.RULE_NAME,
            source: {
                owner: 'AWS',                    // Use AWS-managed rule
                sourceIdentifier: this.SOURCE_IDENTIFIER,
            },
            description: 'Checks whether EBS volumes are backed up as per backup policy.',
        });

        // Define parameters for the remediation action
        const parameters = {
            AutomationAssumeRole: {
                StaticValue: { Values: [automationAssumeRole] }, // Role to execute remediation
            },
            TopicArn: {
                StaticValue: { Values: [snsTopicArn] },          // SNS topic to publish to
            },
            Message: {
                PredefinedValue: { Value: 'CONFIG_EVALUATION_RESULT' }, // Full evaluation result
            },
        };

        // Configure automatic remediation with SNS notification
        const remediationRule = new config.CfnRemediationConfiguration(this, `${this.RULE_NAME}-Remediation`, {
            configRuleName: this.RULE_NAME,
            targetId: 'AWS-PublishSNSNotification',    // Predefined SSM document for SNS
            targetType: 'SSM_DOCUMENT',
            automatic: true,                          // Trigger remediation automatically
            executionControls: {
                ssmControls: {
                    concurrentExecutionRatePercentage: 50, // Limit concurrent executions
                    errorPercentage: 10,                   // Error threshold
                },
            },
            maximumAutomaticAttempts: 3,              // Retry attempts
            parameters: parameters,
            resourceType: 'AWS::EC2::Volume',         // Target resource type
            retryAttemptSeconds: 300,                 // Retry interval
            targetVersion: '1',                       // SSM document version
        });

        // Ensure remediation configuration is created after the Config rule
        remediationRule.node.addDependency(rule);

        // Add a tag to the Config rule for better resource management
        cdk.Tags.of(rule).add('Purpose', 'EBS Backup Compliance');
    }
}
