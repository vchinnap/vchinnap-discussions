import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { aws_config as config, Tags } from 'aws-cdk-lib';
import { BMOLambdaConstruct } from '@bmo-cdk/lambdafunction';
import { BMOSSMDocumentsConstruct } from '@bmo-cdk/ssm-documents';
import * as fs from 'fs';
import * as path from 'path';
import { getContextValues, taggingVars } from '../../utils/context-utils';

export const ruleName = 'hcops-configRule-ec2-resources-protected-by-backup-plan';
export const description = 'evaluates if EC2 instances are protected by a backup plan';

export class Ec2ResourcesProtectedByBackupPlan extends cdk.Stack {
  private readonly lambdaFn: BMOLambdaConstruct;
  private readonly ssmDocumentName: BMOSSMDocumentsConstruct;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const {
      region,
      accountID,
      kmsEncryptionAliasID,
      securityGroupIds,
      subnetIds
    } = getContextValues(this);

    const documentContent = JSON.parse(
      fs.readFileSync(
        path.resolve(__dirname, '../../../../service/lambda-functions/remediations/${ruleName}.json'),
        'utf8'
      )
    );

    const lambdaFn = ruleName;
    const ssmDocumentName = ruleName;
    const hcopsAutomationAssumeRole = `arn:aws:iam::${accountID}:role/HCOPS-AWS-AutomationRole`;
    const bmohcAutomationAssumeRole = `arn:aws:iam::${accountID}:role/bmohc-aws-AutomationRole`;

    // EVALUATION PART
    this.lambdaFn = new BMOLambdaConstruct(this, ruleName + '-ConfigLambda', {
      functionName: lambdaFn,
      functionRelativePath: '../service/lambda-functions/evaluations',
      handler: `${ruleName}.lambda_handler`,
      runtime: 'python3.12',
      tags: taggingVars,
      timeout: 300,
      dynatraceConfig: false,
      existingRoleArn: hcopsAutomationAssumeRole,
      lambdaLogGroupKmsKeyArn: `arn:aws:kms:${region}:${accountID}:alias/${kmsEncryptionAliasID}`,
      subnetIds,
      securityGroupIds,
      lambdaLogRetentionInDays: 7
    });

    const configRule = new config.CustomRule(this, ruleName + '-ConfigRule', {
      configRuleName: ruleName,
      description,
      periodic: true,
      maximumExecutionFrequency: config.MaximumExecutionFrequency.TWENTY_FOUR_HOURS,
      lambdaFunction: this.lambdaFn.lambdaFunction,
      ruleScope: config.RuleScope.fromResource(config.ResourceType.EC2_INSTANCE)
    });

    // Apply tags to the config rule
    for (const [key, value] of Object.entries(taggingVars)) {
      Tags.of(configRule).add(key, value);
    }

    // REMEDIATION PART
    this.ssmDocumentName = new BMOSSMDocumentsConstruct(this, ruleName + '-ConfigSSM', {
      content: documentContent,
      documentFormat: 'JSON',
      documentType: 'Automation',
      name: ssmDocumentName,
      updateMethod: "NewVersion",
      tags: taggingVars
    });

    const configRemediation = new config.CfnRemediationConfiguration(this, ruleName + '-ConfigRemediation', {
      configRuleName: ruleName,
      targetId: ruleName, // Calls SSM Automation document
      targetType: 'SSM_DOCUMENT',
      automatic: false,
      executionControls: {
        ssmControls: {
          concurrentExecutionRatePercentage: 50,
          errorPercentage: 10
        }
      },
      maximumAutomaticAttempts: 3,
      parameters: {
        "InstanceId": {
          ResourceValue: { Value: 'RESOURCE_ID' }
        },
        "AutomationAssumeRole": {
          StaticValue: { Values: [bmohcAutomationAssumeRole] }
        }
      },
      retryAttemptSeconds: 300,
      targetVersion: '1'
    });

    configRemediation.node.addDependency(this.ssmDocumentName);
  }
}
