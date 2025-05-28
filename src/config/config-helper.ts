// lib/constructs/ConfigRuleWithRemediationConstruct.ts
import { Construct } from 'constructs';
import * as cdk from 'aws-cdk-lib';
import { aws_config as config, Tags, CustomResource } from 'aws-cdk-lib';
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

interface RawScopeInput {
  tagKey?: string;
  tagValue?: string;
  complianceResourceTypes?: string[];
}

interface ConfigRuleWithRemediationProps {
  ruleName: string;
  description: string;
  type: 'managed' | 'custom';
  sourceIdentifier?: string;
  evaluationHandler?: string;
  evaluationPath?: string;
  remediationDocs: RemediationDocInput;
  remediationRoleArn: string;
  rawScope?: RawScopeInput;
  tags: Record<string, string>;
  region: string;
  accountId: string;
  subnetIds: string[];
  securityGroupIds: string[];
  kmsKeyAlias: string;
  taggingLambdaPath: string;
  taggingLambdaHandler: string;
  taggingRoleArn: string;
  inputParameters?: Record<string, any>;
  maxFrequency?: config.MaximumExecutionFrequency;
}

export class ConfigRuleWithRemediationConstruct extends Construct {
  private readonly evaluationLambda: BLambdaConstruct;
  private readonly ssmDocument: BSSMDocumentsConstruct;
  constructor(scope: Construct, id: string, props: ConfigRuleWithRemediationProps) {
    super(scope, id);

    const {
      ruleName,
      description,
      type,
      sourceIdentifier,
      evaluationHandler,
      evaluationPath,
      remediationDocs,
      remediationRoleArn,
      rawScope,
      tags,
      region,
      accountId,
      subnetIds,
      securityGroupIds,
      kmsKeyAlias,
      taggingLambdaPath,
      taggingLambdaHandler,
      taggingRoleArn,
      inputParameters,
      maxFrequency
    } = props;

    const resolvedScope = (() => {
      if (rawScope?.tagKey && rawScope?.tagValue) {
        return config.RuleScope.fromTag(rawScope.tagKey, rawScope.tagValue);
      } else if (rawScope?.complianceResourceTypes) {
        return config.RuleScope.fromResources(
          rawScope.complianceResourceTypes.map(t => t as config.ResourceType)
        );
      } else {
        return config.RuleScope.fromResource(config.ResourceType.EC2_INSTANCE);
      }
    })();

    let configRule;

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

      configRule = new config.CustomRule(this, `${ruleName}-ConfigRule`, {
        configRuleName: ruleName,
        description,
        periodic: true,
        maximumExecutionFrequency: config.MaximumExecutionFrequency.ONE_HOUR,
        lambdaFunction: this.evaluationLambda.lambdaFunction,
        ruleScope: resolvedScope
      });
    } else {
      configRule = new config.CfnConfigRule(this, `${ruleName}-ConfigRule`, {
        configRuleName: ruleName,
        source: {
          owner: 'AWS',
          sourceIdentifier: sourceIdentifier!
        },
        description,
        scope: rawScope?.tagKey && rawScope?.tagValue
          ? { tagKey: rawScope.tagKey, tagValue: rawScope.tagValue }
          : rawScope?.complianceResourceTypes
            ? { complianceResourceTypes: rawScope.complianceResourceTypes }
            : undefined
      });
    }
    if(type=='custom'){
      const configRuleArn = configRule.configRuleArn;
    }
    if(type=='managed'){
    const configRuleArn1 = `arn:aws:config:${region}:${accountId}:config-rule/${(configRule as cdk.CfnResource).ref}`;
    }

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

    new CustomResource(this, `${ruleName}-TagCustomResource`, {
      serviceToken: taggingLambda.lambdaFunction.functionArn
    });

    const projectRoot = path.resolve(__dirname, '..', '..', '..');
    const fullRemediationPath = path.resolve(projectRoot, remediationDocs.path);
    if (!fs.existsSync(fullRemediationPath)) {
      throw new Error('Remediation not found in path');
    }
    const docContent = JSON.parse(fs.readFileSync(fullRemediationPath, 'utf8'));

    this.ssmDocument = new BSSMDocumentsConstruct(this, `${ruleName}-SSMDoc`, {
      content: docContent,
      documentFormat: 'JSON',
      documentType: remediationDocs.documentType,
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
      parameters: remediationDocs.parameters,
      retryAttemptSeconds: 300,
      targetVersion: '1'
    });

    configRemediation.node.addDependency(this.ssmDocument);
  }
}
