

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
  ];
}
