import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import {
  aws_config as config,
  Tags as ConfigTags,
  custom_resources as cr,
  aws_logs as logs,
  aws_events as events,
  aws_events_targets as targets,
  CustomResource,
  aws_iam as iam
} from 'aws-cdk-lib';

import { MBOLambdaConstruct } from '@mbo-cdk/lambdafunction';
import { MBOSsmDocumentsConstruct } from '@mbo-cdk/ssm-documents';
import { MBOLWLGConstruct } from '@mbo-cdk/cloudwatch';
import { MBOAWSConfigRuleConstruct } from '@mbo-cdk/aws-config';
import { MBOEventRuleConstruct } from '@mbo-cdk/event-rule';
import { getContextValues, taggingVars } from './context-utils';

import * as fs from 'fs';
import * as path from 'path';

interface RemediationDocInput {
  documentType: 'Automation' | 'Command';
  parameters: Record<string, any>;
}

interface RawScopeInput {
  tagKey?: string;
  tagValue?: string;
  complianceResourceTypes?: config.ResourceType[];
}

interface ConfigRuleWithRemediationProps {
  ruleName: string;
  description: string;
  type: 'managed' | 'custom';
  sourceIdentifier?: string;
  evaluationHandler?: string;
  evaluationPath?: string;
  remediationDoc: RemediationDocInput;
  rScope?: RawScopeInput;
  configRuleScope?: config.RuleScope;
  maximumExecutionFrequency?: config.MaximumExecutionFrequency;
  tags: Record<string, string>;
  region1: string;
  accountID1: string;
  subnetIds1: string[];
  securityGroupIds1: string[];
  kmsEncryptionAliasID1: string;
  taggingLambdaPath: string;
  taggingLambdaHandler: string;
  lambdaRoleArn: string;
  isPeriodic?: boolean;
  inputParameters?: Record<string, any>;
}

export class ConfigRuleWithRemediationConstruct extends Construct {
  private readonly evaluationLambda: MBOLambdaConstruct;
  private readonly taggingLambda: MBOLambdaConstruct;
  private readonly ssmDocument: MBOSsmDocumentsConstruct;

  constructor(scope: Construct, id: string, props: ConfigRuleWithRemediationProps) {
    super(scope, id);

    const { region, accountID, kmsEncryptionAliasID, securityGroupIds, subnetIds, mbohcAutomationAssumeRole, hcopsAutomationAssumeRole } = getContextValues(this);
    const {
      ruleName,
      description,
      type,
      sourceIdentifier,
      evaluationHandler,
      evaluationPath,
      remediationDoc,
      configRuleScope,
      maximumExecutionFrequency,
      tags,
      region1,
      accountID1,
      subnetIds1,
      securityGroupIds1,
      kmsEncryptionAliasID1,
      taggingLambdaPath,
      taggingLambdaHandler,
      lambdaRoleArn,
      isPeriodic,
      inputParameters,
      rScope
    } = props;

    const ruleScope = (() => {
      if (rScope?.tagKey && rScope?.tagValue) {
        return config.RuleScope.fromTag(rScope.tagKey, rScope.tagValue);
      } else if (rScope?.complianceResourceTypes) {
        return config.RuleScope.fromResources(rScope.complianceResourceTypes);
      } else {
        return undefined;
      }
    })();

    const functionRuleName = `${ruleName}-tags`;
    let configRuleArn;

    if (type === 'custom') {
      this.evaluationLambda = new MBOLambdaConstruct(this, `${ruleName}-ConfigLambda`, {
        functionName: ruleName,
        functionRelativePath: '../service/lambda-functions/evaluations',
        handler: `${ruleName}.lambda_handler`,
        runtime: 'python3.12',
        tags,
        timeout: 300,
        dynatraceConfig: false,
        existingRoleArn: lambdaRoleArn,
        lambdaLogGroupKmsKeyArn: `arn:aws:kms:${region}:${accountID}:alias/${kmsEncryptionAliasID}`,
        subnetIds,
        securityGroupIds,
        lambdaLogRetentionInDays: 7
      });

      const customRule = new config.CustomRule(this, `${ruleName}-ConfigRule`, {
        configRuleName: ruleName,
        description,
        ...(maximumExecutionFrequency !== undefined
        ? {
            periodic: true,
            maximumExecutionFrequency: maximumExecutionFrequency ?? config.MaximumExecutionFrequency.TWENTY_FOUR_HOURS
          }
        : {
            configurationChanges: true
        }),
        lambdaFunction: this.evaluationLambda.lambdaFunction,
        ruleScope
      });
      configRuleArn = customRule.configRuleArn;


      const taggingLambda = new MBOLambdaConstruct(this, `${ruleName}-ConfigTagLambda`, {
        functionName: functionRuleName,
        functionRelativePath: '../service/lambda-functions/service',
        handler: 'tags.lambda_handler',
        runtime: 'python3.12',
        tags,
        timeout: 60,
        dynatraceConfig: false,
        existingRoleArn: lambdaRoleArn,
        lambdaLogGroupKmsKeyArn: `arn:aws:kms:${region}:${accountID}:alias/${kmsEncryptionAliasID}`,
        subnetIds,
        securityGroupIds,
        lambdaLogRetentionInDays: 30,
        environmentVariables: {
          CONFIG_RULE_ARN: configRuleArn
        }
      });

      const configTagRule = new CustomResource(this, `${ruleName}-ConfigRuleTags`, {
        serviceToken: taggingLambda.lambdaFunction.functionArn
      });

      customRule.node.addDependency(this.evaluationLambda);
      taggingLambda.node.addDependency(customRule);
      configTagRule.node.addDependency(taggingLambda);
    } else if (type === 'managed') {
      const managedRule = new config.ManagedRule(this, `${ruleName}-ConfigRule`, {
        configRuleName: ruleName,
        description,
        identifier: sourceIdentifier,
        ruleScope
      });
      configRuleArn = managedRule.configRuleArn;

      const taggingLambda = new MBOLambdaConstruct(this, `${ruleName}-ConfigTagLambda`, {
        functionName: functionRuleName,
        functionRelativePath: '../service/lambda-functions/service',
        handler: 'tags.lambda_handler',
        runtime: 'python3.12',
        tags,
        timeout: 60,
        dynatraceConfig: false,
        existingRoleArn: lambdaRoleArn,
        lambdaLogGroupKmsKeyArn: `arn:aws:kms:${region}:${accountID}:alias/${kmsEncryptionAliasID}`,
        subnetIds,
        securityGroupIds,
        lambdaLogRetentionInDays: 1,
        environmentVariables: {
          CONFIG_RULE_ARN: configRuleArn
        }
      });

      const configTagRule = new CustomResource(this, `${ruleName}-ConfigRuleTags`, {
        serviceToken: taggingLambda.lambdaFunction.functionArn
      });

      taggingLambda.node.addDependency(managedRule);
      configTagRule.node.addDependency(taggingLambda);
    }

    const projectRoot = path.resolve(__dirname, '..', '..', '..');
    const fullRemediationPath = path.resolve(projectRoot, `service/lambda-functions/remediations/${ruleName}.json`);
    if (!fs.existsSync(fullRemediationPath)) {
      throw new Error(`Remediation document not found at path: ${fullRemediationPath}`);
    }

    const documentContent = JSON.parse(fs.readFileSync(fullRemediationPath, 'utf-8'));

    this.ssmDocument = new MBOSsmDocumentsConstruct(this, `${ruleName}-ConfigSSM`, {
      content: documentContent,
      documentFormat: 'JSON',
      documentType: remediationDoc.documentType,
      name: ruleName,
      updateMethod: 'NewVersion',
      tags
    });

    const configRemediation = new config.CfnRemediationConfiguration(this, `${ruleName}-ConfigRemediation`, {
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
      parameters: remediationDoc.parameters,
      retryAttemptSeconds: 300,
      targetVersion: '1'
    });

    configRemediation.node.addDependency(this.ssmDocument);
  }
}