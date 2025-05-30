import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import {
  aws_config as config,
  aws_logs as logs,
  aws_events as events,
  aws_events_targets as targets,
} from 'aws-cdk-lib';

import { OMBLambdaConstruct } from '@omb-cdk/lambdafunction';
import { OMBSsmDocumentsConstruct } from '@omb-cdk/ssm-documents';

import * as fs from 'fs';
import * as path from 'path';

interface RemediationDocInput {
  path: string;
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
  region: string;
  accountID: string;
  subnetIds: string[];
  securityGroupIds: string[];
  kmsEncryptionAliasID: string;
  taggingLambdaPath: string;
  taggingLambdaHandler: string;
  lambdaRoleArn: string;
  isPeriodic?: boolean;
  inputParameters?: Record<string, any>;
}

export class ConfigRuleWithRemediationConstruct extends Construct {
  private readonly evaluationLambda: OMBLambdaConstruct;
  private readonly taggingLambda: OMBLambdaConstruct;
  private readonly ssmDocument: OMBSsmDocumentsConstruct;

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
      rScope,
      maximumExecutionFrequency,
      tags,
      region,
      accountID,
      subnetIds,
      securityGroupIds,
      kmsEncryptionAliasID,
      taggingLambdaPath,
      taggingLambdaHandler,
      lambdaRoleArn,
      isPeriodic,
      inputParameters
    } = props;

    const ruleScope = (() => {
      if (rScope?.tagKey && rScope?.tagValue) {
        return config.RuleScope.fromTag(rScope.tagKey, rScope.tagValue);
      } else if (rScope?.complianceResourceTypes?.length) {
        return config.RuleScope.fromResources(rScope.complianceResourceTypes);
      } else {
        return config.RuleScope.fromResource(config.ResourceType.EC2_INSTANCE);
      }
    })();

    const ruleNameSuffix = ruleName.replace(/^hcops-/, '');
    const functionRuleName = `hcops-tags-${ruleNameSuffix}`;

    let configRuleArn: string;

    if (type === 'custom') {
      this.evaluationLambda = new OMBLambdaConstruct(this, `${ruleName}-ConfigLambda`, {
        functionName: ruleName,
        functionRelativePath: evaluationPath!,
        handler: evaluationHandler!,
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
        periodic: isPeriodic ?? true,
        maximumExecutionFrequency: maximumExecutionFrequency ?? config.MaximumExecutionFrequency.ONE_HOUR,
        lambdaFunction: this.evaluationLambda.lambdaFunction,
        ruleScope: ruleScope ?? config.RuleScope.fromResource(config.ResourceType.EC2_INSTANCE)
      });

      configRuleArn = customRule.configRuleArn;
    } else {
      const managedRule = new config.ManagedRule(this, `${ruleName}-ConfigRule`, {
        configRuleName: ruleName,
        identifier: sourceIdentifier!,
        description,
        ruleScope,
        inputParameters
      });

      configRuleArn = managedRule.configRuleArn;
    }

    // ✅ Reusable tagging Lambda for both rule types
    this.taggingLambda = new OMBLambdaConstruct(this, `${ruleName}-ConfigTagLambda`, {
      functionName: functionRuleName,
      functionRelativePath: taggingLambdaPath,
      handler: taggingLambdaHandler,
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

    // ✅ Replace CustomResource with EventBridge rule
    new events.Rule(this, `${ruleName}-ConfigRuleTaggingEvent`, {
      eventPattern: {
        source: ['aws.config'],
        detailType: ['AWS API Call via CloudTrail'],
        detail: {
          eventSource: ['config.amazonaws.com'],
          eventName: ['PutConfigRule']
        }
      },
      targets: [new targets.LambdaFunction(this.taggingLambda.lambdaFunction)]
    });

    // ✅ SSM Document setup
    const projectRoot = path.resolve(__dirname, '..', '..', '..');
    const fullRemediationPath = path.resolve(projectRoot, remediationDoc.path);
    if (!fs.existsSync(fullRemediationPath)) {
      throw new Error(`Remediation document not found at path: ${fullRemediationPath}`);
    }

    const documentContent = JSON.parse(fs.readFileSync(fullRemediationPath, 'utf8'));

    this.ssmDocument = new OMBSsmDocumentsConstruct(this, `${ruleName}-ConfigSSM`, {
      content: documentContent,
      documentFormat: 'JSON',
      documentType: remediationDoc.documentType,
      name: `${ruleName}-ssm`,
      updateMethod: 'NewVersion',
      tags
    });

    const configRemediation = new config.CfnRemediationConfiguration(this, `${ruleName}-ConfigRemediation`, {
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

    const functionCleanupName = `hcops-cleanup-${ruleNameSuffix}`;

    const cleanupLambda = new OMBLambdaConstruct(this, `${ruleName}-ConfigCleanupLambda`, {
        functionName: functionCleanupName,
        functionRelativePath: taggingLambdaPath, // reuse same path/folder
        handler: 'cleanup.handler',              // different entry point in same folder
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
        CONFIG_RULE_NAME: ruleName
        }
    });

    new events.Rule(this, `${ruleName}-ConfigRuleDeletionEvent`, {
    eventPattern: {
        source: ['aws.config'],
        detailType: ['AWS API Call via CloudTrail'],
        detail: {
        eventSource: ['config.amazonaws.com'],
        eventName: ['DeleteConfigRule'],
        requestParameters: {
            configRuleName: [ruleName] // 🔥 exact match with the rule you created
        }
        }
    },
    targets: [new targets.LambdaFunction(cleanupLambda.lambdaFunction)]
    });


    configRemediation.node.addDependency(this.ssmDocument);
  }
}
