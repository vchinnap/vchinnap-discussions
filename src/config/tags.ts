new ConfigRuleWithRemediationConstruct(this, 'OrphanLogGroupRule', {
  ruleName: 'orphan-log-group-check',
  description: 'Detects /aws/lambda/*-tags log groups without a matching Config rule and deletes them',
  type: 'custom',
  sourceIdentifier: 'orphan-log-group-evaluator',
  remediationDocs: {
    path: 'assets/ssm-docs/delete-orphan-log-group.yaml',
    documentType: 'Automation',
    parameters: {
      AutomationAssumeRole: {
        StaticValue: { Values: ['arn:aws:iam::123456789012:role/ConfigRemediationRole'] }
      },
      LogGroupName: {
        ResourceValue: { Value: 'RESOURCE_ID' } // maps to ComplianceResourceId
      }
    }
  },
  remediationRoleArn: 'arn:aws:iam::123456789012:role/ConfigRemediationRole',
  tags: { Environment: 'Prod' },
  region: 'us-east-1',
  accountId: '123456789012',
  subnetIds: ['subnet-abc123'],
  securityGroupIds: ['sg-abc123'],
  kmsKeyAlias: 'kms-log-key',
  taggingLambdaPath: 'lambda/tagger',
  taggingLambdaHandler: 'index.handler',
  taggingRoleArn: 'arn:aws:iam::123456789012:role/TaggingLambdaRole',
  inputParameters: {},
  maxFrequency: config.MaximumExecutionFrequency.TWELVE_HOURS,
  configRuleScope: config.RuleScope.fromTag('Environment', 'Prod')
});
