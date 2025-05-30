import { Stack, StackProps, aws_lambda as lambda, aws_events as events, aws_events_targets as targets } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { RuleMetadata } from './rulemeta';
import * as path from 'path';

export class ConfigRuleStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    // Get all rule names from metadata
    const ruleNames = Object.values(RuleMetadata).map(meta => meta.ruleName);

    // Lambda to process PutConfigRule events
    const watcherLambda = new lambda.Function(this, 'WatcherLambda', {
      runtime: lambda.Runtime.NODEJS_18_X,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '..', 'lambda', 'config-rule-watcher')),
      description: 'Triggered on creation of config rules defined in rulemeta',
    });

    // EventBridge rule to trigger Lambda when a matching Config Rule is created
    new events.Rule(this, 'ConfigRuleCreateEvent', {
      eventPattern: {
        source: ['aws.config'],
        detailType: ['AWS API Call via CloudTrail'],
        detail: {
          eventSource: ['config.amazonaws.com'],
          eventName: ['PutConfigRule'],
          requestParameters: {
            configRule: {
              configRuleName: ruleNames,
            },
          },
        },
      },
      targets: [new targets.LambdaFunction(watcherLambda)],
    });
  }
}
