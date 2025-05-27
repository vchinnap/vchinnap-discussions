new ConfigRuleWithRemediationConstruct(this, 'EbsEncryptionRule', {
  ruleName: 'ec2-ebs-volumes-encrypted',
  description: 'Ensures EBS volumes are encrypted',
  type: 'managed',
  sourceIdentifier: 'EC2_EBS_ENCRYPTION_BY_DEFAULT',
  remediationDocs: [
    {
      path: './remediations/ebs-encryption.json',
      documentType: 'Automation',
      parameters: {
        InstanceId: { ResourceValue: { Value: 'RESOURCE_ID' } },
        EncryptionKey: { StaticValue: { Values: ['alias/aws/ebs'] } },
        AutomationAssumeRole: {
          StaticValue: { Values: ['arn:aws:iam::123456789012:role/AutoRemediateRole'] }
        }
      }
    }
  ],
  remediationRoleArn: 'arn:aws:iam::123456789012:role/AutoRemediateRole',
  tags: taggingVars,
  region,
  accountId,
  kmsKeyAlias,
  subnetIds,
  securityGroupIds,
  taggingLambdaPath: '../service/lambda-functions/tagging',
  taggingLambdaHandler: 'index.lambda_handler',
  taggingRoleArn: 'arn:aws:iam::123456789012:role/TaggingRole'
});
