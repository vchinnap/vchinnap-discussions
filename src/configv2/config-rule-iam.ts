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






import { ConfigRuleIamRoleConstruct } from '../iam/config-rule-iam-role';
import { taggingVars } from '../tags';

const ruleName = 'MyConfigRule';

const ec2DescribePolicy = {
  policyName: `${ruleName}-ec2-describe-policy`,
  policyDocument: {
    Version: '2012-10-17',
    Statement: [
      {
        Sid: 'EC2DescribeAccess',
        Effect: 'Allow',
        Action: ['ec2:DescribeInstances', 'ec2:DescribeTags'],
        Resource: '*'
      }
    ]
  }
};

const cloudwatchMetricsPolicy = {
  policyName: `${ruleName}-cw-metrics-policy`,
  policyDocument: {
    Version: '2012-10-17',
    Statement: [
      {
        Sid: 'CloudWatchMetricsAccess',
        Effect: 'Allow',
        Action: ['cloudwatch:GetMetricData', 'cloudwatch:ListMetrics'],
        Resource: '*'
      }
    ]
  }
};

const ssmAutomationPolicy = {
  policyName: `${ruleName}-ssm-policy`,
  policyDocument: {
    Version: '2012-10-17',
    Statement: [
      {
        Sid: 'SSMAutomationAccess',
        Effect: 'Allow',
        Action: [
          'ssm:StartAutomationExecution',
          'ssm:GetAutomationExecution',
          'ssm:SendCommand'
        ],
        Resource: '*'
      }
    ]
  }
};

const kmsAccessPolicy = {
  policyName: `${ruleName}-kms-policy`,
  policyDocument: {
    Version: '2012-10-17',
    Statement: [
      {
        Sid: 'KMSDecryptAccess',
        Effect: 'Allow',
        Action: [
          'kms:Decrypt',
          'kms:DescribeKey',
          'kms:GenerateDataKey'
        ],
        Resource: [
          'arn:aws:kms:ca-central-1:123456789012:key/abc12345-6789-1234-aaaa-bbbbbbbbbbbb'
        ]
      }
    ]
  }
};

const ruleIam = new ConfigRuleIamRoleConstruct(this, `IAM-${ruleName}`, {
  ruleName,
  assumeServices: ['lambda.amazonaws.com', 'ssm.amazonaws.com'],
  inlinePolicies: [
    ec2DescribePolicy,
    cloudwatchMetricsPolicy,
    ssmAutomationPolicy,
    kmsAccessPolicy
  ],
  tags: taggingVars
});
