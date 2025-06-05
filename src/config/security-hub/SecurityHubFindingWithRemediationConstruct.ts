import { Construct } from 'constructs';
import {
  aws_events as events,
  aws_events_targets as targets,
  aws_logs as logs,
  aws_lambda as lambda,
  aws_ssm as ssm,
  aws_iam as iam
} from 'aws-cdk-lib';
import * as fs from 'fs';
import * as path from 'path';
import { MBOLambdaConstruct } from '@mbo-cdk/lambdafunction';
import { MBOSsmDocumentsConstruct } from '@mbo-cdk/ssm-documents';
import { SecurityHubFindingWithRemediationProps } from './types';

export class SecurityHubFindingWithRemediationConstruct extends Construct {
  constructor(scope: Construct, id: string, props: SecurityHubFindingWithRemediationProps) {
    super(scope, id);

    const {
      controlId,
      controlTitle,
      controlDescription,
      relatedRequirements,
      severity,
      evaluationLambdaPath,
      evaluationHandler,
      remediationDoc,
      productArn,
      resources,
      tags,
      lambdaRoleArn,
      subnetIds,
      securityGroupIds,
      kmsAlias,
      region,
      accountId
    } = props;

    // 1. Evaluation Lambda
    const evalLambda = new MBOLambdaConstruct(this, `${controlId}-EvalLambda`, {
      functionName: `${controlId}-evaluation`,
      functionRelativePath: evaluationLambdaPath,
      handler: evaluationHandler,
      runtime: 'python3.12',
      tags,
      timeout: 300,
      dynatraceConfig: false,
      existingRoleArn: lambdaRoleArn,
      lambdaLogGroupKmsKeyArn: `arn:aws:kms:${region}:${accountId}:alias/${kmsAlias}`,
      subnetIds,
      securityGroupIds,
      lambdaLogRetentionInDays: 7,
      environmentVariables: {
        SECURITY_HUB_PRODUCT_ARN: productArn,
        GENERATOR_ID: controlId,
        COMPLIANCE_TITLE: controlTitle,
        COMPLIANCE_DESCRIPTION: controlDescription,
        SEVERITY: severity,
        RESOURCE_TYPES: JSON.stringify(resources),
        SECURITY_CONTROL_ID: controlId,
        RELATED_REQUIREMENTS: JSON.stringify(relatedRequirements)
      }
    });

    // 2. Remediation SSM Document
    const projectRoot = path.resolve(__dirname, '..', '..', '..');
    const fullRemediationPath = path.resolve(projectRoot, `service/lambda-functions/remediations/${controlId}.json`);
    if (!fs.existsSync(fullRemediationPath)) {
      throw new Error(`Remediation document not found: ${fullRemediationPath}`);
    }
    const documentContent = JSON.parse(fs.readFileSync(fullRemediationPath, 'utf-8'));

    const ssmDoc = new MBOSsmDocumentsConstruct(this, `${controlId}-SSMDoc`, {
      name: controlId,
      content: documentContent,
      documentFormat: 'JSON',
      documentType: remediationDoc.documentType,
      updateMethod: 'NewVersion',
      tags
    });

    // 3. EventBridge Rule for Remediation Trigger
    new events.Rule(this, `${controlId}-RemediateOnFinding`, {
      eventPattern: {
        source: ['aws.securityhub'],
        detailType: ['Security Hub Findings - Imported'],
        detail: {
          findings: {
            GeneratorId: [controlId],
            Compliance: { Status: ['FAILED'] }
          }
        }
      },
      targets: [
        new targets.SsmAutomationTarget({
          documentName: controlId,
          parameters: remediationDoc.parameters
        })
      ]
    });
  }
}
