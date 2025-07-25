export function getCwAlarmActionCheckPolicies(ruleName: string, accountID: string, region: string): any[] {
  const cloudwatchPermissions = {
    Sid: 'DescribeAlarms',
    Effect: 'Allow',
    Action: [
      'cloudwatch:DescribeAlarms',
      'cloudwatch:ListTagsForResource'
    ],
    Resource: '*'
  };

  const ec2Describe = {
    Sid: 'DescribeInstances',
    Effect: 'Allow',
    Action: [
      'ec2:DescribeInstances',
      'ec2:DescribeTags'
    ],
    Resource: '*'
  };

  const configEvaluation = {
    Sid: 'PutConfigEvaluations',
    Effect: 'Allow',
    Action: ['config:PutEvaluations'],
    Resource: '*'
  };

  return [
    {
      policyName: `${ruleName}-cw-action-check-policy`,
      policyDocument: {
        Version: '2012-10-17',
        Statement: [
          cloudwatchPermissions,
          ec2Describe,
          configEvaluation
        ]
      }
    }
  ];
}
