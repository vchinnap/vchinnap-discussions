new events.Rule(this, 'ConfigRuleDeleteEvent', {
  eventPattern: {
    source: ['aws.config'],
    detailType: ['AWS API Call via CloudTrail'],
    detail: {
      eventSource: ['config.amazonaws.com'],
      eventName: ['DeleteConfigRule'],
    },
  },
  targets: [new targets.LambdaFunction(cleanupLambda)],
});
