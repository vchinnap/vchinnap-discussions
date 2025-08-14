{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "KMSForLambdaLogs",
      "Effect": "Allow",
      "Action": [
        "kms:Encrypt",
        "kms:Decrypt",
        "kms:ReEncrypt*",
        "kms:GenerateDataKey*",
        "kms:DescribeKey",
        "kms:CreateGrant",
        "kms:RetireGrant"
      ],
      "Resource": "arn:aws:kms:${Region}:${AccountId}:key/${KeyId}",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "${Region}",
          "kms:ViaService": "logs.${Region}.amazonaws.com"
        },
        "ForAnyValue:StringLike": {
          "kms:ResourceAliases": "alias/lambda-logs*"
        },
        "StringLike": {
          "kms:EncryptionContext:aws:logs:arn": "arn:aws:logs:${Region}:${AccountId}:log-group:/aws/lambda/*"
        },
        "Bool": {
          "kms:GrantIsForAWSResource": "true"
        }
      }
    },
    {
      "Sid": "KMSListAndAliasRead",
      "Effect": "Allow",
      "Action": [
        "kms:ListAliases",
        "kms:ListKeys",
        "kms:ListGrants",
        "kms:DescribeKey"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "${Region}"
        }
      }
    },
    {
      "Sid": "DenyKMSOutsideSafePath",
      "Effect": "Deny",
      "Action": "kms:*",
      "Resource": "*",
      "Condition": {
        "StringNotEquals": {
          "aws:RequestedRegion": "${Region}"
        }
      }
    },
    {
      "Sid": "LogsScoped",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:PutRetentionPolicy",
        "logs:AssociateKmsKey"
      ],
      "Resource": "arn:aws:logs:${Region}:${AccountId}:log-group:/aws/lambda/*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "${Region}"
        }
      }
    },
    {
      "Sid": "ConfigAPISafeguards",
      "Effect": "Allow",
      "Action": [
        "config:GetComplianceDetailsByConfigRule",
        "config:GetComplianceDetailsByResource",
        "config:GetComplianceSummaryByResourceType",
        "config:DescribeComplianceByConfigRule",
        "config:DescribeComplianceByResource",
        "config:DescribeRemediationConfigurations",
        "config:SelectResourceConfig",
        "config:PutRemediationConfigurations",
        "config:StartRemediationExecution",
        "config:StartConfigRulesEvaluation",
        "config:PutEvaluations",
        "config:DeleteConfigRule",
        "config:TagResource",
        "config:DescribeConfigRules"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "${Region}"
        },
        "ForAnyValue:StringEquals": {
          "aws:CalledVia": [
            "config.amazonaws.com"
          ]
        }
      }
    },
    {
      "Sid": "AllowTaggedConfigRulesOnly",
      "Effect": "Allow",
      "Action": [
        "config:DeleteConfigRule",
        "config:TagResource"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:ResourceTag/Owner": "HCOPS"
        }
      }
    },
    {
      "Sid": "SSMAutomationForRemediation",
      "Effect": "Allow",
      "Action": [
        "ssm:StartAutomationExecution",
        "ssm:GetAutomationExecution"
      ],
      "Resource": [
        "arn:aws:ssm:${Region}:${AccountId}:automation-definition/HOPS-ConfigRule-Rule-1:$DEFAULT",
        "arn:aws:ssm:${Region}:${AccountId}:automation-definition/HOPS-ConfigRule-Rule-2:$DEFAULT"
      ],
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "${Region}"
        }
      }
    },
    {
      "Sid": "LambdaInvokeFromSSM",
      "Effect": "Allow",
      "Action": "lambda:InvokeFunction",
      "Resource": "arn:aws:lambda:${Region}:${AccountId}:function:HOPS-Remediate-*"
    }
  ]
}
