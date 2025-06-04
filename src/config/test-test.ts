const customRule = new config.CustomRule(this, `${ruleName}-ConfigRule`, {
  configRuleName: ruleName,
  description,
  lambdaFunction: this.evaluationLambda.lambdaFunction,
  ruleScope,
  inputParameters,
  ...(isPeriodic !== undefined || maximumExecutionFrequency !== undefined
    ? {
        periodic: isPeriodic ?? true,
        maximumExecutionFrequency: maximumExecutionFrequency ?? config.MaximumExecutionFrequency.TWENTY_FOUR_HOURS
      }
    : {
        periodic: false
      })
});
