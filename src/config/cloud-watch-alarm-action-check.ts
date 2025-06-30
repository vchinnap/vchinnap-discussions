new ConfigRuleWithRemediationConstruct(this, 'CloudWatchAlarmStrictCheckRule', {
  ruleName: 'cloudwatch-alarm-action-check',
  description: 'Checks CloudWatch Alarms for required ALARM state actions with approved ARNs.',
  type: 'managed',
  sourceIdentifier: config.ManagedRuleIdentifiers.CLOUDWATCH_ALARM_ACTION_CHECK,
  inputParameters: {
    alarmActionRequired: 'true',
    insufficientDataActionRequired: 'false',
    okActionRequired: 'false',
    action1: 'arn:aws:sns:us-east-1:123456789012:CriticalAlertTopic',
    action2: 'arn:aws:autoscaling:us-east-1:123456789012:scalingPolicy:abc:autoScalingGroupName/my-asg'
  },
  rScope: {
    tagKey: 'ConfigRule',
    tagValue: 'True'
  },
  lambdaRoleArn: hcopsAutomationAssumeRole,
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
