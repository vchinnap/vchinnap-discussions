new ConfigRuleWithRemediationConstruct(this, 'CustomEBSOptimizationRule', {
  ruleName: 'ebs-optimization-check',
  description: 'Ensure EC2 instances are EBS optimized',
  type: 'custom',
  evaluationHandler: 'index.handler',
  evaluationPath: 'lambda/evaluation',
  remediationDocs: {
    path: 'assets/ssm-docs/ebs-optimize.json',
    documentType: 'Automation',
    parameters: {
      InstanceId: {
        ResourceValue: { Value: 'RESOURCE_ID' }
      }
    }
  },
  remediationRoleArn: 'arn:aws:iam::123456789012:role/ConfigRemediationRole',
  tags: { Team: 'CloudOps' },
  region: 'us-east-1',
  accountId: '123456789012',
  subnetIds: ['subnet-xyz456'],
  securityGroupIds: ['sg-xyz456'],
  kmsKeyAlias: 'kms-log-key',
  taggingLambdaPath: 'lambda/tagger',
  taggingLambdaHandler: 'index.handler',
  taggingRoleArn: 'arn:aws:iam::123456789012:role/TaggingLambdaRole',
  configRuleScope: config.RuleScope.fromResource(config.ResourceType.EC2_INSTANCE)
});
