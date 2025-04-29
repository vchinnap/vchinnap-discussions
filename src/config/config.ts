import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import { BMAWSConfigRuleConstruct } from './index'; // your custom construct

export class WindowsConfigRuleStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const ruleLambda = new lambda.Function(this, 'WindowsConfigRuleLambda', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'index.lambda_handler',
      code: lambda.Code.fromAsset('lambda'),
      timeout: cdk.Duration.minutes(5),
    });

    ruleLambda.addToRolePolicy(new iam.PolicyStatement({
      actions: [
        'cloudwatch:DescribeAlarms',
        'config:PutEvaluations',
      ],
      resources: ['*'],
    }));

    new BMAWSConfigRuleConstruct(this, 'WindowsCustomConfigRule', {
      source: {
        owner: 'CUSTOM_LAMBDA',
        sourceIdentifier: ruleLambda.functionArn,
      },
      configRuleName: 'windows-memory-disk-alarm-check',
      description: 'Checks alarms for Windows EC2s with Config=True',
      maximumExecutionFrequency: 'Six_Hours',
    });
  }
}
