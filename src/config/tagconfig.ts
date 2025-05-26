import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { aws_config as config, Tags, CfnCustomResource } from 'aws-cdk-lib';
import { BLambdaConstruct } from '@b-cdk/lambdafunction';
import { BSSMDocumentsConstruct } from '@o-cdk/ssm-documents';
import * as fs from 'fs';
import * as path from 'path';
import { getContextValues, taggingVars } from '../../utils/context-utils';

export const ruleName = 'hcops-configRule-ec2-resources-protected-by-backup-plan';
export const description = 'evaluates if EC2 instances are protected by a backup plan';

export class Ec2ResourcesProtectedByBackupPlan extends cdk.Stack {
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
        path.resolve(__dirname, `../../../../service/lambda-functions/remediations/${ruleName}.json`),
        'utf8'
      )
    );

    const hcopsAutomationAssumeRole = `arn:aws:iam::${accountID}:role/HCOPS-AWS-AutomationRole`;
    const bmohcAutomationAssumeRole = `arn:aws:iam::${accountID}:role/bmohc-aws-AutomationRole`;

    const evaluationLambda = new BLambdaConstruct(this, ruleName + '-ConfigLambda', {
      functionName: ruleName,
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
      lambdaFunction: evaluationLambda.lambdaFunction,
      ruleScope: config.RuleScope.fromResource(config.ResourceType.EC2_INSTANCE)
    });

    for (const [key, value] of Object.entries(taggingVars)) {
      Tags.of(configRule).add(key, value);
    }

    const configRuleArn = configRule.configRuleArn;

    // ✅ Use reduce() instead of Object.fromEntries for environment variables
    const tagEnvVars = Object.entries(taggingVars).reduce((acc, [k, v]) => {
      acc[`TAG_${k}`] = v;
      return acc;
    }, {} as Record<string, string>);

    const taggingLambda = new BLambdaConstruct(this, ruleName + '-TagLambda', {
      functionName: ruleName + '-tagger',
      functionRelativePath: '../service/lambda-functions/tagging',
      handler: 'index.lambda_handler',
      runtime: 'python3.12',
      tags: taggingVars,
      timeout: 60,
      dynatraceConfig: false,
      existingRoleArn: hcopsAutomationAssumeRole,
      lambdaLogGroupKmsKeyArn: `arn:aws:kms:${region}:${accountID}:alias/${kmsEncryptionAliasID}`,
      subnetIds,
      securityGroupIds,
      lambdaLogRetentionInDays: 7,
      environmentVariables: {
        CONFIG_RULE_ARN: configRuleArn,
        ...tagEnvVars
      }
    });

    const tagCustomResource = new CfnCustomResource(this, ruleName + '-TagCustomResource', {
      serviceToken: taggingLambda.lambdaFunction.functionArn,
    });

    for (const [key, value] of Object.entries(taggingVars)) {
      Tags.of(taggingLambda.lambdaFunction).add(key, value);
      Tags.of(tagCustomResource).add(key, value);
    }

    const remediationDoc = new BSSMDocumentsConstruct(this, ruleName + '-ConfigSSM', {
      content: documentContent,
      documentFormat: 'JSON',
      documentType: 'Automation',
      name: ruleName,
      updateMethod: 'NewVersion',
      tags: taggingVars
    });

    const configRemediation = new config.CfnRemediationConfiguration(this, ruleName + '-ConfigRemediation', {
      configRuleName: ruleName,
      targetId: ruleName,
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
        InstanceId: {
          ResourceValue: { Value: 'RESOURCE_ID' }
        },
        AutomationAssumeRole: {
          StaticValue: { Values: [bmohcAutomationAssumeRole] }
        }
      },
      retryAttemptSeconds: 300,
      targetVersion: '1'
    });

    configRemediation.node.addDependency(remediationDoc);
  }
}
