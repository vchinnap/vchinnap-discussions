import { getCommonPolicyStatements } from './common-policy';

export function getCleanupOrphanLogGroupsPolicies(ruleName: string, accountID: string, region: string): any[] {
  const scopedDelete = {
    Sid: 'ScopedDeleteOrphanLogs',
    Effect: 'Allow',
    Action: ['logs:DeleteLogGroup', 'logs:ListTagsLogGroup'],
    Resource: `arn:aws:logs:${region}:${accountID}:log-group:/aws/lambda/*-tags`
  };

  return [
    {
      policyName: `${ruleName}-combined-policy`,
      policyDocument: {
        Version: '2012-10-17',
        Statement: [
          ...getCommonPolicyStatements(accountID, region),
          scopedDelete
        ]
      }
    }
  ];
}





export function getCommonPolicyStatements(accountID: string, region: string): any[] {
  return [
    // ✅ Logging
    {
      Sid: 'WriteToCWLogs',
      Effect: 'Allow',
      Action: [
        'logs:CreateLogGroup',
        'logs:CreateLogStream',
        'logs:PutLogEvents'
      ],
      Resource: '*'
    },

    // ✅ SSM Remediation Support
    {
      Sid: 'SSMAutomation',
      Effect: 'Allow',
      Action: [
        'ssm:StartAutomationExecution',
        'ssm:GetAutomationExecution',
        'ssm:DescribeAutomationExecutions',
        'ssm:GetDocument',
        'ssm:ListDocuments',
        'ssm:ListDocumentVersions'
      ],
      Resource: '*'
    },

    // ✅ CloudWatch Metrics
    {
      Sid: 'CWMetricRead',
      Effect: 'Allow',
      Action: [
        'cloudwatch:GetMetricData',
        'cloudwatch:ListMetrics',
        'cloudwatch:DescribeAlarms'
      ],
      Resource: '*'
    }
  ];
}
