export interface SecurityHubFindingWithRemediationProps {
  controlId: string;
  controlTitle: string;
  controlDescription: string;
  relatedRequirements: string[];
  severity: 'INFORMATIONAL' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

  evaluationLambdaPath: string;
  evaluationHandler: string;

  remediationDoc: {
    documentType: 'Automation' | 'Command';
    parameters: Record<string, any>;
  };

  productArn: string;
  resources: string[]; // e.g., ['AwsEc2Instance']
  tags?: Record<string, string>;
  lambdaRoleArn: string;
  subnetIds: string[];
  securityGroupIds: string[];
  kmsAlias: string;
  region: string;
  accountId: string;
}
