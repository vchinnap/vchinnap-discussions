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
        const region = process.env.TargetAccountRegion;
        
        // Define Config Rule Name
        const ruleName = 'hcops-ec2-volume-in-use-check';

        // AWS Managed Rule for EBS Backup Plan Validation
        const sourceIdentifier = 'EBS_IN_BACKUP_PLAN';

        // Define SNS Topic for notifications
        const snsTopicArn = `arn:aws:sns:${region}:${accountID}:HC-PATCH-SBX-TOPIC`;

        // Define IAM Role for SSM Automation Execution
        const automationAssumeRole = `arn:aws:iam::${accountID}:role/HC-AWS-AutomationRole`;

        // Create SSM Automation Document (Runbook)
        const customDocument = new ssm.CfnDocument(this, 'CustomConfigNotification', {
            content: {
                schemaVersion: '0.3',
                description: 'Custom notification for AWS Config non-compliance',
                parameters: {
                    AutomationAssumeRole: { type: 'String' },
                    TopicArn: { type: 'String' },
                    resourceId: { type: 'String' },
                },
                mainSteps: [
                    {
                        name: 'GetComplianceDetails',
                        action: 'aws:executeAwsApi',
                        inputs: {
                            Service: 'config',
                            Api: 'GetComplianceDetailsByResource',
                            ResourceType: 'AWS::EC2::Volume',
                            ResourceId: '{{ resourceId }}',
                        },
                        outputs: [
                            { Name: 'ComplianceType', Selector: '$.EvaluationResults[0].ComplianceType', Type: 'String' },
                            { Name: 'Annotation', Selector: '$.EvaluationResults[0].Annotation', Type: 'String' },
                        ],
                    },
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
ComplianceType: {ComplianceType}
Details: {Annotation}""".format(**event)
    return {"message": msg}
                            `.trim(),
                            InputPayload: {
                                resourceId: '{{ resourceId }}',
                                ComplianceType: '{{ GetComplianceDetails.ComplianceType }}',
                                Annotation: '{{ GetComplianceDetails.Annotation }}',
                            },
                        },
                        outputs: [
                            { Name: 'message', Selector: '$.Payload.message', Type: 'String' },
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

        // Define parameters for the remediation action
        const parameters = {
            AutomationAssumeRole: { StaticValue: { Values: [automationAssumeRole] } },
            TopicArn: { StaticValue: { Values: [snsTopicArn] } },
            resourceId: { ResourceValue: { Value: 'RESOURCE_ID' } },
        };

        // Define AWS Config Rule (EBS Backup Plan Check)
        const rule = new BMAWSConfigRuleConstruct(this, ruleName, {
            configRuleName: ruleName,
            source: { owner: 'AWS', sourceIdentifier: sourceIdentifier },
            description: 'Checks whether EBS volumes are backed up as per backup policy.',
        });

        // Create AWS Config Remediation Configuration
        const remediationRule = new config.CfnRemediationConfiguration(this, ruleName + '-Remediation', {
            configRuleName: rule.configRuleName,
            targetId: 'CustomConfigNotification',
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
