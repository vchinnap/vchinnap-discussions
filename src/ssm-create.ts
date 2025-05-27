// lib/constructs/ConfigRuleWithRemediationConstruct.ts
import { Construct } from 'constructs';
import * as cdk from 'aws-cdk-lib';
import { aws_config as config, Tags, CustomResource, aws_logs as logs } from 'aws-cdk-lib';
import * as cr from 'aws-cdk-lib/custom-resources';
import * as fs from 'fs';
import * as path from 'path';
import { BLambdaConstruct } from '@bmo-cdk/lambdafunction';
import { BSSMDocumentsConstruct } from '@bmo-cdk/ssm-documents';

interface RemediationDocInput {
  path: string;
  documentType: 'Automation' | 'Command';
  parameters: Record<string, any>;
}

interface ConfigRuleWithRemediationProps {
  ruleName: string;
  description: string;
  type: 'managed' | 'custom';
  sourceIdentifier?: string;
  evaluationHandler?: string;
  evaluationPath?: string;
  remediationDoc: RemediationDocInput;
  remediationRoleArn: string;
  configRuleScope?: config.RuleScope;
  maximumExecutionFrequency?: config.MaximumExecutionFrequency;
  tags: Record<string, string>;
  region: string;
  accountId: string;
  subnetIds: string[];
  securityGroupIds: string[];
  kmsKeyAlias: string;
  taggingLambdaPath: string;
  taggingLambdaHandler: string;
  taggingRoleArn: string;
}

export class ConfigRuleWithRemediationConstruct extends Construct {
  private readonly evaluationLambda?: BLambdaConstruct;
  private readonly configRule: config.ManagedRule | config.CustomRule;

  constructor(scope: Construct, id: string, props: ConfigRuleWithRemediationProps) {
    super(scope, id);

    const {
      ruleName,
      description,
      type,
      sourceIdentifier,
      evaluationHandler,
      evaluationPath,
      remediationDoc,
      remediationRoleArn,
      configRuleScope,
      maximumExecutionFrequency,
      tags,
      region,
      accountId,
      subnetIds,
      securityGroupIds,
      kmsKeyAlias,
      taggingLambdaPath,
      taggingLambdaHandler,
      taggingRoleArn
    } = props;

    if (type === 'custom') {
      this.evaluationLambda = new BLambdaConstruct(this, `${ruleName}-EvalLambda`, {
        functionName: `${ruleName}-eval`,
        functionRelativePath: evaluationPath!,
        handler: evaluationHandler!,
        runtime: 'python3.12',
        tags,
        timeout: 300,
        dynatraceConfig: false,
        existingRoleArn: taggingRoleArn,
        lambdaLogGroupKmsKeyArn: `arn:aws:kms:${region}:${accountId}:alias/${kmsKeyAlias}`,
        subnetIds,
        securityGroupIds,
        lambdaLogRetentionInDays: 7
      });

      this.configRule = new config.CustomRule(this, `${ruleName}-ConfigRule`, {
        configRuleName: ruleName,
        description,
        periodic: true,
        maximumExecutionFrequency: maximumExecutionFrequency ?? config.MaximumExecutionFrequency.ONE_HOUR,
        lambdaFunction: this.evaluationLambda.lambdaFunction,
        ruleScope: configRuleScope ?? config.RuleScope.fromResource(config.ResourceType.EC2_INSTANCE)
      });
    } else {
      this.configRule = new config.ManagedRule(this, `${ruleName}-ConfigRule`, {
        configRuleName: ruleName,
        description,
        identifier: sourceIdentifier!,
        ruleScope: configRuleScope ?? config.RuleScope.fromResource(config.ResourceType.EC2_INSTANCE)
      });
    }

    const configRuleArn = this.configRule.configRuleArn;

    const taggingLambda = new BLambdaConstruct(this, `${ruleName}-TagLambda`, {
      functionName: `${ruleName}-tagger`,
      functionRelativePath: taggingLambdaPath,
      handler: taggingLambdaHandler,
      runtime: 'python3.12',
      tags,
      timeout: 60,
      dynatraceConfig: false,
      existingRoleArn: taggingRoleArn,
      lambdaLogGroupKmsKeyArn: `arn:aws:kms:${region}:${accountId}:alias/${kmsKeyAlias}`,
      subnetIds,
      securityGroupIds,
      lambdaLogRetentionInDays: 7,
      environmentVariables: {
        CONFIG_RULE_ARN: configRuleArn
      }
    });

    const logGroup = new logs.LogGroup(this, `${ruleName}-TagLambdaLogGroup`, {
      logGroupName: `/aws/lambda/${taggingLambda.lambdaFunction.functionName}`,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      retention: logs.RetentionDays.ONE_WEEK
    });
    logGroup.node.addDependency(taggingLambda.lambdaFunction);

    const tagResource = new CustomResource(this, `${ruleName}-TagCustomResource`, {
      serviceToken: taggingLambda.lambdaFunction.functionArn
    });

    tagResource.node.addDependency(this.configRule);
    tagResource.node.addDependency(taggingLambda);
    tagResource.node.addDependency(logGroup);
    if (this.evaluationLambda) {
      this.configRule.node.addDependency(this.evaluationLambda);
    }

    if (!remediationDoc.path) {
      throw new Error(`Missing path in remediationDoc for rule: ${ruleName}`);
    }

    const docPath = path.join(__dirname, '..', '..', remediationDoc.path);
    const docContent = JSON.parse(fs.readFileSync(docPath, 'utf8'));

    const ssmDocument = new BSSMDocumentsConstruct(this, `${ruleName}-SSMDoc`, {
      content: docContent,
      documentFormat: 'JSON',
      documentType: remediationDoc.documentType,
      name: `${ruleName}-ssm`,
      updateMethod: 'NewVersion',
      tags
    });

    const configRemediation = new config.CfnRemediationConfiguration(this, `${ruleName}-Remediation`, {
      configRuleName: ruleName,
      targetId: `${ruleName}-ssm`,
      targetType: 'SSM_DOCUMENT',
      automatic: false,
      executionControls: {
        ssmControls: {
          concurrentExecutionRatePercentage: 50,
          errorPercentage: 10
        }
      },
      maximumAutomaticAttempts: 3,
      parameters: remediationDoc.parameters,
      retryAttemptSeconds: 300,
      targetVersion: '1'
    });

    configRemediation.node.addDependency(ssmDocument);
  }
}
