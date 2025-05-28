import * as cdk from 'aws-cdk-lib';
import * as aws_config from 'aws-cdk-lib/aws-config';

const app = new cdk.App();
const stack = new cdk.Stack(app, 'ConfigRuleStack');

// Define a Config rule
const configRule = new aws_config.CfnConfigRule(stack, 'MyConfigRule', {
  configRuleName: 'my-config-rule',
  source: {
    owner: 'AWS',
    sourceIdentifier: 'IAM_PASSWORD_POLICY',
  },
  tags: [
    {
      key: 'Environment',
      value: 'Production',
    },
    {
      key: 'Department',
      value: 'Security',
    },
  ],
});

app.synth();
