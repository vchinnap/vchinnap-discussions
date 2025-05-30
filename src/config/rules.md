
# 🛡️ AWS CDK: Config Rule with Remediation and Tagging

This CDK construct provisions an AWS **managed Config rule**, sets up optional **remediation using SSM documents**, and applies **tags** via a Lambda function using `CustomResource`.

---

## ✅ What It Does

- Provisions a managed AWS Config rule using `ManagedRule`
- Applies remediation using an SSM Automation or Command document
- Applies tags to the Config rule using a Lambda function (triggered via `CustomResource`)
- Supports multiple resource types, KMS encryption, periodic evaluations, and scoped targeting

---

## 🔧 Usage Example

```ts
new ConfigRuleWithRemediationConstruct(this, 'S3PublicAccessConfigRule', {
  ruleName: 'hcops-s3-public-blocked',
  description: 'Ensures S3 buckets block public access',
  type: 'managed',
  sourceIdentifier: config.ManagedRuleIdentifiers.S3_BUCKET_PUBLIC_READ_PROHIBITED,
  remediationDoc: {
    path: 'remediations/managed/s3-remediate-public-access.json',
    documentType: 'Automation',
    parameters: {
      BucketName: {
        StaticValue: 'target-s3-bucket'
      }
    }
  },
  ruleScopeInput: {
    complianceResourceTypes: [
      config.ResourceType.S3_BUCKET
    ]
  },
  region: this.region,
  accountID: this.account,
  tags: {
    Environment: 'prod',
    Owner: 'cloud-team'
  },
  subnetIds: ['subnet-abc123'],
  securityGroupIds: ['sg-xyz789'],
  kmsEncryptionAliasID: 'alias/my-key',
  taggingLambdaPath: 'lambda/tag-config-rule',
  taggingLambdaHandler: 'index.handler',
  lambdaRoleArn: 'arn:aws:iam::123456789012:role/existing-lambda-role',
});
```

---

## 🧱 File Structure

```
lib/
  constructs/
    ConfigRuleWithRemediationConstruct.ts
  remediations/
    managed/
      s3-remediate-public-access.json
lambda/
  tag-config-rule/
    index.py
```

---

## 🪄 Features

| Feature              | Description                                                                 |
|----------------------|-----------------------------------------------------------------------------|
| Managed Rule         | Uses `config.ManagedRule` with AWS built-in identifiers                     |
| Remediation          | Deploys SSM document using `CfnRemediationConfiguration`                    |
| Lambda-based Tagging | Tags Config rules via Lambda triggered through `CustomResource`             |
| KMS Encryption       | Uses KMS keys for Lambda log group encryption                               |
| Scoped Evaluation    | Tag-based or resource-type-based rule scoping supported                     |

---

## 🧩 Prerequisites

- CDK v2 installed
- IAM role with:
  - `config:TagResource`
  - `ssm:CreateDocument`, `ssm:UpdateDocument`, etc.
- Lambda for tagging with `CONFIG_RULE_ARN` environment variable

---

## 📚 References

- [CDK ManagedRule Docs](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_config.ManagedRule.html)
- [AWS Config Managed Rules](https://docs.aws.amazon.com/config/latest/developerguide/managed-rules-by-aws-config.html)
- [AWS Config Remediation Docs](https://docs.aws.amazon.com/config/latest/developerguide/remediation.html)

---

## 🧾 ConfigRuleWithRemediationProps Table

| Name                      | Description                                                                                         |
|:--------------------------|:----------------------------------------------------------------------------------------------------|
| ruleName                  | The name of the AWS Config rule.                                                                    |
| description               | Description of the Config rule.                                                                     |
| type                      | Specifies whether the rule is managed or custom.                                                    |
| sourceIdentifier          | The identifier for the managed rule (required for managed rules).                                   |
| evaluationHandler         | The handler for the evaluation Lambda (required for custom rules).                                  |
| evaluationPath            | The path to the Lambda source (required for custom rules).                                          |
| remediationDoc            | SSM remediation document configuration.                                                             |
| ruleScopeInput            | Defines the resource scope of the rule using either tag-based targeting or resource type filtering. |
| configRuleScope           | Explicit AWS Config RuleScope override.                                                             |
| maximumExecutionFrequency | How often AWS Config evaluates the rule.                                                            |
| tags                      | Tags to assign to the rule, Lambdas, and documents.                                                 |
| region                    | AWS region.                                                                                         |
| accountID                 | AWS account ID.                                                                                     |
| subnetIds                 | Subnets for Lambda VPC configuration.                                                               |
| securityGroupIds          | Security groups for Lambda networking.                                                              |
| kmsEncryptionAliasID      | KMS alias used for encrypting Lambda log groups.                                                    |
| taggingLambdaPath         | Path to the tagging Lambda code.                                                                    |
| taggingLambdaHandler      | Handler for the tagging Lambda function.                                                            |
| lambdaRoleArn             | IAM role ARN for Lambdas.                                                                           |
| isPeriodic                | Defines if a custom rule is evaluated periodically.                                                 |
| inputParameters           | Parameters passed to managed rules (if applicable).                                                 |