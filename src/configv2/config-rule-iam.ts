import { ConfigRuleIamRoleConstruct } from '../iam/config-rule-iam-role';
import { getDiskAlarmRulePolicies } from '../utils/config-rule-policies/disk-alarm-rule-policy';
import { taggingVars } from '../tags';

const ruleName = 'DiskAlarmRule';
const accountID = this.node.tryGetContext('accountID');

const ruleIam = new ConfigRuleIamRoleConstruct(this, `IAM-${ruleName}`, {
  ruleName,
  assumeServices: ['lambda.amazonaws.com', 'ssm.amazonaws.com'],
  inlinePolicies: getDiskAlarmRulePolicies(ruleName, accountID),
  tags: taggingVars
});
