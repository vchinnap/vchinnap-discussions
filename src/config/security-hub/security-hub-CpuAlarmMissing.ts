import { SecurityHubFindingWithRemediationConstruct } from '../constructs/SecurityHubFindingWithRemediationConstruct';

export class CpuAlarmMissing extends Construct {
  constructor(scope: Construct, id: string) {
    super(scope, id);

    new SecurityHubFindingWithRemediationConstruct(this, 'BMO.EC2.1-Finding', {
      controlId: 'BMO.EC2.1',
      controlTitle: 'Ensure CPUUtilization alarm exists for EC2',
      controlDescription: 'EC2 with ConfigRule=True tag must have a CloudWatch alarm for CPU.',
      relatedRequirements: ['BMO-Policy-3.2', 'Internal-GRC-EC2-101'],
      severity: 'HIGH',

      evaluationLambdaPath: '../service/lambda-functions/evaluations',
      evaluationHandler: 'missing_cpu_alarm.lambda_handler',

      remediationDoc: {
        documentType: 'Automation',
        parameters: {
          InstanceId: { StaticValue: 'i-0123456789abcdef0' },
          AutomationAssumeRole: { StaticValue: 'arn:aws:iam::123456789012:role/automation-role' }
        }
      },

      productArn: `arn:aws:securityhub:${this.region}:${this.account}:product/${this.account}/default`,
      resources: ['AwsEc2Instance'],
      tags: {
        Owner: 'PlatformTeam',
        Standard: 'BMO-Security'
      },
      lambdaRoleArn: 'arn:aws:iam::123456789012:role/lambda-exec-role',
      subnetIds: ['subnet-abc', 'subnet-def'],
      securityGroupIds: ['sg-xyz'],
      kmsAlias: 'kms-bmo-default',
      region: this.region,
      accountId: this.account
    });
  }
}
