import * as cdk from 'aws-cdk-lib';
import * as config from 'aws-cdk-lib/aws-config';
import { Construct } from 'constructs';

class EbsBackupPlanRule extends cdk.Stack {
    constructor(scope: Construct, id: string, props?: cdk.StackProps) {
        super(scope, id, props);

        const ruleName = "EbsBackupRule";
        const ssmDocumentName = "AWS-PublishSNSNotification"; // SSM document to publish SNS messages
        const resourceType = "AWS::EC2::Volume"; // Targets EBS volumes
        const snsTopicArn = "arn:aws:sns:us-east-1:123456789012:MyTopic"; // Replace with your SNS topic ARN
        const assumeRoleArn = "arn:aws:iam::123456789012:role/AWSConfigRemediationRole"; // Replace with your IAM role ARN

        // JSON message payload with dynamic volume ID
        const messagePayload = JSON.stringify({
            environment: "Production",
            alert_type: "EBS Backup Compliance Violation",
            resource_info: {
                volume_id: "{ResourceId}" // Placeholder for the non-compliant volume ID
            }
        });

        // Define the remediation configuration
        const remediationRule = new config.CfnRemediationConfiguration(this, ruleName + '-Remediation', {
            configRuleName: ruleName,
            targetId: ssmDocumentName,  // SSM document for remediation
            targetType: 'SSM_DOCUMENT',
            automatic: true,
            executionControls: {
                ssmControls: {
                    concurrentExecutionRatePercentage: 50,
                    errorPercentage: 10
                }
            },
            maximumAutomaticAttempts: 3, // Number of retry attempts
            parameters: {
                TopicArn: {
                    StaticValue: { Values: [snsTopicArn] }
                },
                Message: {
                    StaticValue: { Values: [messagePayload] }
                },
                Subject: {
                    StaticValue: { Values: ["EBS Backup Compliance Alert"] }
                },
                AutomationAssumeRole: {
                    StaticValue: { Values: [assumeRoleArn] }
                }
            },
            resourceType: resourceType, // Specifies EBS volumes
            retryAttemptSeconds: 300, // Retry delay in seconds
            targetVersion: '1'
        });
    }
}

export default EbsBackupPlanRule;
