import * as cdk from 'aws-cdk-lib';
import * as config from 'aws-cdk-lib/aws-config';
import { Construct } from 'constructs';

class EbsBackupPlanRule extends cdk.Stack {
    constructor(scope: Construct, id: string, props?: cdk.StackProps) {
        super(scope, id, props);

        // Configuration details
        const ruleName = "EbsBackupRule";
        const ssmDocumentName = "AWS-PublishSNSNotification"; // Custom SSM document
        const resourceType = "AWS::EC2::Volume"; // Targets EBS volumes
        const snsTopicArn = "arn:aws:sns:us-east-1:123456789012:MyTopic"; // Replace with your SNS topic ARN
        const assumeRoleArn = "arn:aws:iam::123456789012:role/AWSConfigRemediationRole"; // Replace with your IAM role ARN

        // Define the message payload (customize as needed)
        const messagePayload = JSON.stringify({
            environment: "Production",
            alert_type: "EBS Backup Compliance Violation",
            resource_info: {
                volume_id: "See ResourceId in notification"
            }
        });

        // Define the remediation configuration
        const remediationRule = new config.CfnRemediationConfiguration(this, `${ruleName}-Remediation`, {
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
                Subject: {
                    StaticValue: { Values: ["EBS Backup Compliance Alert"] }
                },
                Message: {
                    StaticValue: { Values: [messagePayload] }
                },
                ResourceId: {
                    ResourceValue: { Value: 'RESOURCE_ID' } // Tells AWS Config to use the resource’s ID
                },
                AutomationAssumeRole: {
                    StaticValue: { Values: [assumeRoleArn] }
                }
            },
            resourceType: resourceType, // Targets EBS volumes
            retryAttemptSeconds: 300, // Retry delay in seconds
            targetVersion: '1'
        });
    }
}

export default EbsBackupPlanRule;
