new ConfigRuleWithRemediationConstruct(this, 'S3PublicReadRule', {
  ruleName: 's3-bucket-public-read-prohibited',
  description: 'Ensures S3 buckets do not allow public read access',
  type: 'managed',
  sourceIdentifier: 'S3_BUCKET_PUBLIC_READ_PROHIBITED',
  remediationDocs: {
    path: 'assets/ssm-docs/s3-remediation.json',
    documentType: 'Automation',
    parameters: {
      BucketName: {
        StaticValue: { Values: ['dummy-bucket'] }
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
  maxFrequency: config.MaximumExecutionFrequency.TWENTY_FOUR_HOURS,
  configRuleScope: config.RuleScope.fromTag('Environment', 'Prod')
});
