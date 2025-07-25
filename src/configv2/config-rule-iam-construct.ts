// lib/iam/config-rule-iam-role.ts

import { Construct } from 'constructs';
import { MBOIAMRoleConstruct } from '@mbo-cdk/iam';

export interface InlinePolicyEntry {
  policyName: string;
  policyDocument: {
    Version: string;
    Statement: any[];
  };
}

export interface ConfigRuleIamRoleProps {
  ruleName: string;
  assumeServices: string[]; // e.g., ['lambda.amazonaws.com', 'ssm.amazonaws.com']
  inlinePolicies: InlinePolicyEntry[];
  tags?: Record<string, string>;
  exceptionCode?: string[];
}

export class ConfigRuleIamRoleConstruct extends Construct {
  public readonly roleArn: string;

  constructor(scope: Construct, id: string, props: ConfigRuleIamRoleProps) {
    super(scope, id);

    const {
      ruleName,
      assumeServices,
      inlinePolicies,
      tags = {},
      exceptionCode = ['E043', 'E049', 'E037', 'E045']
    } = props;

    const assumeRolePolicyDocument = {
      Version: '2012-10-17',
      Statement: assumeServices.map(service => ({
        Sid: `Assume${service.replace(/\./g, '')}`,
        Effect: 'Allow',
        Principal: {
          Service: service
        },
        Action: 'sts:AssumeRole'
      }))
    };

    const role = new MBOIAMRoleConstruct(this, `${ruleName}-IamRole`, {
      roleName: `${ruleName}-iam-role`,
      roleDescription: `IAM role for AWS Config Rule: ${ruleName}`,
      pathoverride: '/',
      associatedAppCatID: ['1'],
      assumeRolePolicyDocument,
      policies: inlinePolicies,
      tags,
      exceptionCode
    });

    this.roleArn = role.role.roleArn;
  }
}
