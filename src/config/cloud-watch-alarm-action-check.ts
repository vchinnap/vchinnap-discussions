new ConfigRuleWithRemediationConstruct(this, `${ruleName}-configrule`, {
  ruleName,
  description,
  type: 'managed',
  sourceIdentifier: config.ManagedRuleIdentifiers.CLOUDWATCH_ALARM_ACTION_CHECK,

  inputParameters: {
    alarmActionRequired: 'true',
    insufficientDataActionRequired: 'false',
    okActionRequired: 'false'
  },

  rScope: {
    tagKey: 'ConfigRule',
    tagValue: 'True'
  },

  lambdaRoleArn: hcopsAutomationAssumeRole,
  tags: taggingVars,
  automatic: false,

  remediationDoc: {
    documentType: 'Automation',
    parameters: {
      AlarmName: {
        ResourceValue: { Value: 'RESOURCE_ID' }
      },
      AutomationAssumeRole: {
        StaticValue: { Values: [hcopsAutomationAssumeRole] }
      },
      ActionArn: {
        StaticValue: { Values: ['arn:aws:sns:us-east-1:123456789012:CriticalAlertTopic'] }
      }
    }
  }
});
