// lib/utils/config-rule-policies/cleanup-orphan-loggroups-policy.ts

export function getCleanupOrphanLogGroupsPolicies(ruleName: string, accountID: string): any[] {
  return [
    {
      policyName: `${ruleName}-logs-cleanup-policy`,
      policyDocument: {
        Version: '2012-10-17',
        Statement: [
          // 🧹 Clean up orphan log groups
          {
            Sid: 'ManageLogGroups',
            Effect: 'Allow',
            Action: [
              'logs:DescribeLogGroups',
              'logs:DeleteLogGroup',
              'logs:ListTagsLogGroup'
            ],
            Resource: '*'
          },

          // 📝 Lambda evaluation log write access
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

          // ⚙️ SSM Automation execution for remediation
          {
            Sid: 'SSMExecution',
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

          // (Optional) 🔐 KMS permissions for encrypted log groups or SSM doc
          {
            Sid: 'KMSAccess',
            Effect: 'Allow',
            Action: [
              'kms:Decrypt',
              'kms:Encrypt',
              'kms:DescribeKey',
              'kms:GenerateDataKey'
            ],
            Resource: [`arn:aws:kms:ca-central-1:${accountID}:key/<your-key-id>`]
          }
        ]
      }
    }
  ];
}
