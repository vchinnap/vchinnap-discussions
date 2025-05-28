import { Construct } from 'constructs';
import * as cdk from 'aws-cdk-lib';
import { aws_config as config, CustomResource } from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as fs from 'fs';
import * as path from 'path';
import { BLambdaConstruct } from '@bmo-cdk/lambdafunction';
import { BSSMDocumentsConstruct } from '@bmo-cdk/ssm-documents';


maximumExecutionFrequency: type === 'custom' || periodicManagedRuleIdentifiers.includes(sourceIdentifier!)
  ? maxFrequency ?? config.MaximumExecutionFrequency.TWENTY_FOUR_HOURS
  : undefined


interface RemediationDocInput {
  path: string;
  documentType: 'Automation' | 'Command';
  parameters: Record<string, any>;
}

interface CfnScope {
  complianceResourceTypes?: string[];
  tagKey?: string;
  tagValue?: string;
  complianceResourceId?: string;
}

interface ConfigRuleWithRemediationProps {
  ruleName: string;
  description: string;
  type: 'managed' | 'custom';
  sourceIdentifier?: string;
  evaluationHandler?: string;
  evaluationPath?: string;
  periodic?: boolean;
  maximumExecutionFrequency?: config.MaximumExecutionFrequency;
  remediationDocs: RemediationDocInput[];
  remediationRoleArn: string;
  configRuleScope?: config.RuleScope;
  cfnScope?: CfnScope;
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
  constructor(scope: Construct, id: string, props: ConfigRuleWithRemediationProps) {
    super(scope, id);

    const {
      ruleName,
      description,
      type,
      sourceIdentifier,
      evaluationHandler,
      evaluationPath,
      periodic,
      maximumExecutionFrequency,
      remediationDocs,
      remediationRoleArn,
      configRuleScope,
      cfnScope,
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

    let configRule: config.CfnConfigRule;
    let evaluationLambda;

    if (type === 'custom') {
      evaluationLambda = new BLambdaConstruct(this, `${ruleName}-EvalLambda`, {
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

      // ✅ Allow AWS Config to invoke the Lambda
      evaluationLambda.lambdaFunction.addPermission(`${ruleName}-AllowConfigInvoke`, {
        principal: new iam.ServicePrincipal('config.amazonaws.com'),
        action: 'lambda:InvokeFunction',
        sourceArn: `arn:aws:config:${region}:${accountId}:config-rule/${ruleName}`
      });

      configRule = new config.CfnConfigRule(this, `${ruleName}-ConfigRule`, {
        configRuleName: ruleName,
        description,
        source: {
          owner: 'CUSTOM_LAMBDA',
          sourceIdentifier: evaluationLambda.lambdaFunction.functionArn,
          sourceDetails: [
            {
              eventSource: 'aws.config',
              messageType: periodic
                ? 'ScheduledNotification'
                : 'ConfigurationItemChangeNotification'
            }
          ]
        },
        scope: cfnScope,
        maximumExecutionFrequency: periodic
          ? (maximumExecutionFrequency ?? config.MaximumExecutionFrequency.ONE_HOUR)
          : undefined
      });

    } else {
      configRule = new config.CfnConfigRule(this, `${ruleName}-ConfigRule`, {
        configRuleName: ruleName,
        description,
        source: {
          owner: 'AWS',
          sourceIdentifier: sourceIdentifier!
        },
        scope: cfnScope
      });
    }

    // ✅ Apply tags
    Object.entries(tags).forEach(([key, value]) => {
      cdk.Tags.of(configRule).add(key, value);
    });

    const configRuleArn = `arn:aws:config:${region}:${accountId}:config-rule/${configRule.ref}`;

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

    remediationDocs.forEach((doc, idx) => {
      const docContent = JSON.parse(
        fs.readFileSync(path.resolve(__dirname, doc.path), 'utf8')
      );

      const ssmDocument = new BSSMDocumentsConstruct(this, `${ruleName}-SSMDoc${idx + 1}`, {
        content: docContent,
        documentFormat: 'JSON',
        documentType: doc.documentType,
        name: `${ruleName}-ssm-${idx + 1}`,
        updateMethod: 'NewVersion',
        tags
      });

      new config.CfnRemediationConfiguration(this, `${ruleName}-Remediation${idx + 1}`, {
        configRuleName: ruleName,
        targetId: `${ruleName}-ssm-${idx + 1}`,
        targetType: 'SSM_DOCUMENT',
        automatic: false,
        executionControls: {
          ssmControls: {
            concurrentExecutionRatePercentage: 50,
            errorPercentage: 10
          }
        },
        maximumAutomaticAttempts: 3,
        parameters: doc.parameters,
        retryAttemptSeconds: 300,
        targetVersion: '1'
      });
    });
  }
}
