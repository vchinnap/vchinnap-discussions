import * as cdk from 'aws-cdk-lib';
import { BMAWSConfigRuleConstruct } from '@bmo-cdk/aws-config';
import { Construct } from 'constructs';
import { aws_config as config, aws_ssm as ssm } from 'aws-cdk-lib';

export class EbsBackupPlanRule extends cdk.Stack {
    constructor(scope: Construct, id: string, props?: cdk.StackProps) {
        super(scope, id, props);

        // Retrieve values from CDK context or environment variables
        const stage = this.node.tryGetContext('Stage');
        const accountID = this.node.tryGetContext('accountID');
        const stageShortCode = this.node.tryGetContext('stageShortCode');
        const regionShortCode = this.node.tryGetContext('regionShortCode');
        const region = process.env.TargetAccountRegion;

        // Define Config Rule Name
        const ruleName = 'hcops-ec2-volume-in-use-check';

        // AWS Managed Rule for EBS Backup Plan Validation
        const sourceIdentifier = 'EBS_IN_BACKUP_PLAN';

        // Define SNS Topic for notifications
        const snsTopicArn = `arn:aws:sns:${region}:${accountID}:HC-PATCH-SBX-TOPIC`;

        // Define IAM Role for SSM Automation Execution
        const automationAssumeRole = `arn:aws:iam::${accountID}:role/HC-AWS-AutomationRole`;

        // Define Custom SSM Document for dynamic notifications
        const customDocument = new ssm.CfnDocument(this, 'CustomConfigNotification', {
            content: {
                schemaVersion: '0.3',
                description: 'Custom notification for AWS Config non-compliance',
                parameters: {
                    AutomationAssumeRole: { type: 'String' },
                    TopicArn: { type: 'String' },
                    resourceId: { type: 'String' },
                    resourceType: { type: 'String' },
                    complianceType: { type: 'String' },
                    accountId: { type: 'String' },
                    awsRegion: { type: 'String' },
                    configRuleName: { type: 'String' },
                    annotation: { type: 'String' },
                },
                mainSteps: [
                    {
                        name: 'ConstructMessage',
                        action: 'aws:executeScript',
                        inputs: {
                            Runtime: 'python3.8',
                            Handler: 'handler',
                            Script: `
def handler(event, context):
    msg = """AWS Config non-compliant resource.
ResourceId: {resourceId}
ResourceType: {resourceType}
ComplianceType: {complianceType}
AWS Account ID: {accountId}
AWS Region: {awsRegion}
Config Rule Name: {configRuleName}
Details: {annotation}""".format(**event)
    return {"message": msg}
                            `.trim(),
                            InputPayload: {
                                resourceId: '{{ resourceId }}',
                                resourceType: '{{ resourceType }}',
                                complianceType: '{{ complianceType }}',
                                accountId: '{{ accountId }}',
                                awsRegion: '{{ awsRegion }}',
                                configRuleName: '{{ configRuleName }}',
                                annotation: '{{ annotation }}',
                            },
                        },
                        outputs: [
                            {
                                Name: 'message',
                                Selector: '$.Payload.message',
                                Type: 'String',
                            },
                        ],
                    },
                    {
                        name: 'PublishToSNS',
                        action: 'aws:executeAwsApi',
                        inputs: {
                            Service: 'sns',
                            Api: 'Publish',
                            TopicArn: '{{ TopicArn }}',
                            Message: '{{ ConstructMessage.message }}',
                        },
                    },
                ],
            },
            documentType: 'Automation',
            name: 'CustomConfigNotification',
        });

        // Define parameters with dynamic values for the custom SSM document
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

        // Define AWS Config Rule (EBS Backup Plan Check)
        const rule = new BMAWSConfigRuleConstruct(this, ruleName, {
            configRuleName: ruleName,
            source: {
                owner: 'AWS',
                sourceIdentifier: sourceIdentifier,
            },
            description: 'Checks whether EBS volumes are backed up as per backup policy.',
        });

        // Create Remediation Configuration for non-compliant resources
        const remediationRule = new config.CfnRemediationConfiguration(this, ruleName + '-Remediation', {
            configRuleName: rule.configRuleName,
            targetId: 'CustomConfigNotification', // Use custom document
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
            targetVersion: '1',
        });

        // Ensure remediation executes after Config rule and custom document creation
        remediationRule.node.addDependency(rule);
        remediationRule.node.addDependency(customDocument);
    }
}
