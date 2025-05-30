| Name                      | Type                             | Description                                                                                         |
|:--------------------------|:---------------------------------|:----------------------------------------------------------------------------------------------------|
| ruleName                  | string                           | The name of the AWS Config rule.                                                                    |
| description               | string                           | Description of the Config rule.                                                                     |
| type                      | 'managed' | 'custom'             | Specifies whether the rule is managed or custom.                                                    |
| sourceIdentifier          | string                           | The identifier for the managed rule (required for managed rules).                                   |
| evaluationHandler         | string                           | The handler for the evaluation Lambda (required for custom rules).                                  |
| evaluationPath            | string                           | The path to the Lambda source (required for custom rules).                                          |
| remediationDoc            | RemediationDocInput              | SSM remediation document configuration.                                                             |
| ruleScopeInput            | RawScopeInput                    | Defines the resource scope of the rule using either tag-based targeting or resource type filtering. |
| configRuleScope           | config.RuleScope                 | Explicit AWS Config RuleScope override.                                                             |
| maximumExecutionFrequency | config.MaximumExecutionFrequency | How often AWS Config evaluates the rule.                                                            |
| tags                      | Record<string, string>           | Tags to assign to the rule, Lambdas, and documents.                                                 |
| region                    | string                           | AWS region.                                                                                         |
| accountID                 | string                           | AWS account ID.                                                                                     |
| subnetIds                 | string[]                         | Subnets for Lambda VPC configuration.                                                               |
| securityGroupIds          | string[]                         | Security groups for Lambda networking.                                                              |
| kmsEncryptionAliasID      | string                           | KMS alias used for encrypting Lambda log groups.                                                    |
| taggingLambdaPath         | string                           | Path to the tagging Lambda code.                                                                    |
| taggingLambdaHandler      | string                           | Handler for the tagging Lambda function.                                                            |
| lambdaRoleArn             | string                           | IAM role ARN for Lambdas.                                                                           |
| isPeriodic                | boolean                          | Defines if a custom rule is evaluated periodically.                                                 |
| inputParameters           | Record<string, any>              | Parameters passed to managed rules (if applicable).                                                 |