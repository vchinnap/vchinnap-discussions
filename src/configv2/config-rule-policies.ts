// lib/utils/config-rule-policies/disk-alarm-rule-policy.ts

export function getDiskAlarmRulePolicies(ruleName: string, accountID: string) {
  return [
    {
      policyName: `${ruleName}-ec2-disk-metrics`,
      policyDocument: {
        Version: '2012-10-17',
        Statement: [
          {
            Sid: 'EC2DescribeInstances',
            Effect: 'Allow',
            Action: ['ec2:DescribeInstances'],
            Resource: '*'
          },
          {
            Sid: 'CWGetMetrics',
            Effect: 'Allow',
            Action: ['cloudwatch:GetMetricData', 'cloudwatch:ListMetrics'],
            Resource: '*'
          }
        ]
      }
    }
  ];
}
