import { Construct } from 'constructs';
import * as process from 'process';

export interface ContextValues {
  stage: string;
  region: string;
  accountID: string;
  stageShortCode: string;
  regionShortCode: string;
  accShortCode: string;
  kmsEncryptionAliasID: string;
  subnetIds: string[];
  securityGroupIds: string[];
}

export function getContextValues(scope: Construct): ContextValues {
  const stage = scope.node.tryGetContext('stage');         // e.g., sbx
  const accountID = scope.node.tryGetContext('accountID'); // e.g., 1
  const stageShortCode = scope.node.tryGetContext('stageShortCode');
  const regionShortCode = scope.node.tryGetContext('regionShortCode');
  const region = process.env.TargetAccountRegion || 'us-east-1';
  const accShortCode = process.env.AccountShortCode || 'DEFAULT';

  let kmsEncryptionAliasID = '';
  if (region === 'ca-central-1') {
    kmsEncryptionAliasID = `BMO-${accShortCode}-CAC1-CloudWatchLogs`;
  } else if (region === 'us-east-1') {
    kmsEncryptionAliasID = `BMO-${accShortCode}-USE1-CloudWatchLogs`;
  } else {
    kmsEncryptionAliasID = `BMO-${accShortCode}-GENERIC-CloudWatchLogs`;
  }

  const infraMap: Record<string, { subnets: string[]; sgs: string[] }> = {
    'sbx-1-ca-central-1': {
      subnets: ['subnet-sbx1-cac1-a', 'subnet-sbx1-cac1-b'],
      sgs: ['sg-sbx1-cac1-001']
    },
    'sbx-1-us-east-1': {
      subnets: ['subnet-sbx1-use1-a', 'subnet-sbx1-use1-b'],
      sgs: ['sg-sbx1-use1-001']
    },
    'sbx-2-ca-central-1': {
      subnets: ['subnet-sbx2-cac1-a', 'subnet-sbx2-cac1-b'],
      sgs: ['sg-sbx2-cac1-001']
    },
    'dev-1-ca-central-1': {
      subnets: ['subnet-dev1-cac1-a', 'subnet-dev1-cac1-b'],
      sgs: ['sg-dev1-cac1-001']
    },
    'prod-1-us-east-1': {
      subnets: ['subnet-prod1-use1-a', 'subnet-prod1-use1-b'],
      sgs: ['sg-prod1-use1-001']
    },
    'prod-2-us-east-1': {
      subnets: ['subnet-prod2-use1-a', 'subnet-prod2-use1-b'],
      sgs: ['sg-prod2-use1-001']
    }
    // Add more combinations here
  };

  const key = `${stage}-${accountID}-${region}`;
  const { subnets = [], sgs = [] } = infraMap[key] || {};

  return {
    stage,
    region,
    accountID,
    stageShortCode,
    regionShortCode,
    accShortCode,
    kmsEncryptionAliasID,
    subnetIds: subnets,
    securityGroupIds: sgs
  };
}
