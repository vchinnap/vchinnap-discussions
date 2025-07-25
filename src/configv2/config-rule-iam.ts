const ruleIam = new ConfigRuleIamRoleConstruct(this, 'IAM-MyConfigRule', {
  ruleName: 'MyConfigRule',
  assumeServices: [
    'lambda.amazonaws.com',
    'ssm.amazonaws.com',
    'config.amazonaws.com'
  ],
  inlinePolicies: [
    {
      policyName: 'basic-access',
      policyDocument: {
        Version: '2012-10-17',
        Statement: [
          {
            Sid: 'EC2Describe',
            Effect: 'Allow',
            Action: ['ec2:DescribeInstances'],
            Resource: '*'
          }
        ]
      }
    }
  ],
  tags: taggingVars
});
