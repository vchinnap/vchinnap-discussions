new ConfigRuleWithRemediationConstruct(this, `${ruleName}-configrule`, {
  ruleName,
  description: 'Checks if CloudWatch alarms have an action configured for the ALARM, INSUFFICIENT_DATA, or OK state.',
  type: 'managed',
  sourceIdentifier: config.ManagedRuleIdentifiers.CLOUDWATCH_ALARM_ACTION_CHECK,

  inputParameters: {
    alarmActionRequired: 'true',
    insufficientDataActionRequired: 'true',
    okActionRequired: 'true'
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
      }
    }
  }
});
