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






export function getCwAlarmActionRuleAndRemediationPolicies(ruleName: string, accountID: string, region: string): any[] {
  return [
    {
      policyName: `${ruleName}-cw-action-full-policy`,
      policyDocument: {
        Version: '2012-10-17',
        Statement: [
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

          // ✅ CloudWatch read (metrics and alarms)
          {
            Sid: 'CWMetricRead',
            Effect: 'Allow',
            Action: [
              'cloudwatch:GetMetricData',
              'cloudwatch:ListMetrics',
              'cloudwatch:DescribeAlarms',
              'cloudwatch:ListTagsForResource'
            ],
            Resource: '*'
          },

          // ✅ EC2 tag filtering for scoping alarms
          {
            Sid: 'DescribeInstances',
            Effect: 'Allow',
            Action: [
              'ec2:DescribeInstances',
              'ec2:DescribeTags'
            ],
            Resource: '*'
          },

          // ✅ Report compliance to AWS Config
          {
            Sid: 'PutEvaluations',
            Effect: 'Allow',
            Action: ['config:PutEvaluations'],
            Resource: '*'
          },

          // ✅ Remediation: Enable or Disable alarm actions
          {
            Sid: 'EnableDisableAlarmActions',
            Effect: 'Allow',
            Action: [
              'cloudwatch:EnableAlarmActions',
              'cloudwatch:DisableAlarmActions'
            ],
            Resource: '*'
          },

          // ✅ Allow to assume Automation role if needed (defensive)
          {
            Sid: 'AllowPassAutomationRole',
            Effect: 'Allow',
            Action: 'iam:PassRole',
            Resource: `arn:aws:iam::${accountID}:role/HCOPS-AWS-AutomationRole`
          }
        ]
      }
    }
  ];
}
