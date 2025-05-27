new ConfigRuleWithRemediationConstruct(this, 'BackupPlanRule', {
  ruleName: 'hcops-configRule-ec2-resources-protected-by-backup-plan',
  description: 'Evaluates if EC2 instances are protected by a backup plan',
  type: 'custom',
  evaluationHandler: 'hcops-configRule-ec2-resources-protected-by-backup-plan.lambda_handler',
  evaluationPath: '../service/lambda-functions/evaluations', // path to your custom rule logic
  remediationDocs: [
    {
      path: './remediations/hcops-configRule-ec2-resources-protected-by-backup-plan.json',
      documentType: 'Automation',
      parameters: {
        InstanceId: {
          ResourceValue: { Value: 'RESOURCE_ID' }
        },
        AutomationAssumeRole: {
          StaticValue: { Values: ['arn:aws:iam::123456789012:role/HCOPS-AWS-AutomationRole'] }
        }
      }
    }
  ],
  remediationRoleArn: 'arn:aws:iam::123456789012:role/HCOPS-AWS-AutomationRole',
  configRuleScope: config.RuleScope.fromResource(config.ResourceType.EC2_INSTANCE),
  tags: {
    Environment: 'Production',
    Team: 'CloudOps'
  },
  region: 'us-east-1',
  accountId: '123456789012',
  kmsKeyAlias: 'kms-hcops-key',
  subnetIds: ['subnet-abc123'],
  securityGroupIds: ['sg-xyz456'],
  taggingLambdaPath: '../service/lambda-functions/tagging',
  taggingLambdaHandler: 'index.lambda_handler',
  taggingRoleArn: 'arn:aws:iam::123456789012:role/TaggingRole'
});
