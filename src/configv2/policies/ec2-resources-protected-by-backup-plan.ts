export function getEc2BackupProtectionPolicies(ruleName: string, accountID: string, region: string): any[] {
  const ec2Describe = {
    Sid: 'DescribeEC2Instances',
    Effect: 'Allow',
    Action: [
      'ec2:DescribeInstances',
      'ec2:DescribeTags'
    ],
    Resource: '*'
  };

  const backupPermissions = {
    Sid: 'BackupPlanAccess',
    Effect: 'Allow',
    Action: [
      'backup:ListBackupPlans',
      'backup:GetBackupPlan',
      'backup:ListBackupVaults',
      'backup:GetBackupVaultAccessPolicy',
      'backup:ListProtectedResources',
      'backup:ListTags',
      'backup:ListBackupSelections',
      'backup:GetBackupSelection',
      'backup:ListRecoveryPointsByResource',
      'backup:GetRecoveryPointRestoreMetadata',
      'backup:StartBackupJob',
      'backup:CreateBackupSelection'
    ],
    Resource: '*'
  };

  const configEvaluation = {
    Sid: 'PutConfigEvaluations',
    Effect: 'Allow',
    Action: ['config:PutEvaluations'],
    Resource: '*'
  };

  const passAutomationRole = {
    Sid: 'AllowPassAutomationRole',
    Effect: 'Allow',
    Action: 'iam:PassRole',
    Resource: `arn:aws:iam::${accountID}:role/HCOPS-AWS-AutomationRole`
  };

  return [
    {
      policyName: `${ruleName}-ec2-backup-check-policy`,
      policyDocument: {
        Version: '2012-10-17',
        Statement: [
          ec2Describe,
          backupPermissions,
          configEvaluation,
          passAutomationRole
        ]
      }
    }
  ];
}
