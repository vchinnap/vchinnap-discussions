import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as config from 'aws-cdk-lib/aws-config';

// ✅ BMOLambdaConstruct as you provided
export interface BMOLambdaProps {
  functionName: string;
  functionRelativePath: string;
  handler: string;
  runtime: lambda.Runtime;
  tags?: { [key: string]: string };
}

export class BMOLambdaConstruct extends Construct {
  public readonly lambdaFunction: lambda.Function;

  constructor(scope: Construct, id: string, props: BMOLambdaProps) {
    super(scope, id);

    this.lambdaFunction = new lambda.Function(this, 'Lambda', {
      functionName: props.functionName,
      code: lambda.Code.fromAsset(props.functionRelativePath),
      handler: props.handler,
      runtime: props.runtime,
    });

    if (props.tags) {
      for (const [key, value] of Object.entries(props.tags)) {
        cdk.Tags.of(this.lambdaFunction).add(key, value);
      }
    }
  }
}

// ✅ Main stack class
export class CloudWatchAlarmCustomResourceChecks extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Instantiate the custom lambda construct
    const windowsMetricsLambda = new BMOLambdaConstruct(this, 'WindowsMetricsLambdaConstruct', {
      functionName: 'winConfigureRuleLambda',
      functionRelativePath: '../service/lambda-functions/windows-metrics',
      handler: 'windows-metrics.lambda_handler',
      runtime: lambda.Runtime.PYTHON_3_12,
      tags: {
        Cost_Center: 'H9196',
        AppCatID: '7777775',
        Support_Team: 'RUN CLOUD OPS',
      },
    });

    // AWS Config custom rule using the lambdaFunction from your construct
    const windowsMemoryDiskAlarmRule = new config.CustomRule(this, 'WindowsMemoryDiskAlarmRule', {
      configRuleName: 'windows-memory-disk-metrics',
      description: 'Checks alarms for Windows EC2s with Config=True',
      configurationChanges: true,
      periodic: false,
      maximumExecutionFrequency: config.MaximumExecutionFrequency.TWENTY_FOUR_HOURS,
      lambdaFunction: windowsMetricsLambda.lambdaFunction, // ✅ fixed here
      ruleScope: config.RuleScope.fromResources([
        config.ResourceType.EC2_INSTANCE,
      ]),
    });

    windowsMemoryDiskAlarmRule.node.addDependency(windowsMetricsLambda.lambdaFunction);
  }
}
