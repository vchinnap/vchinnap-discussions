import { Stack } from 'aws-cdk-lib';

export class ContextUtils {
  static getCommitId(scope: Stack): string {
    const commitId = scope.node.tryGetContext('commitId');
    if (!commitId) {
      throw new Error('Missing context value: commitId. Pass via --context commitId=abc123.');
    }
    return commitId;
  }
}


const stage = process.env.Stage;
const id = process.env.AccountIdentifier;

const validStages = ["prod", "sbx"];
const validIds = ["1", "2", "3"];

if ((validStages.includes(stage) && validIds.includes(id)) || stage === "shr" || stage === "ops") {
  stack = new vindstack();
}






const originalRuleName = 'OPS-ConfigRule-EC2-Resources-Protected-By-Backup-Plan';

// Remove "OPS" and "ConfigRule"
const trimmedRuleName = originalRuleName
  .replace('OPS-', '')
  .replace('ConfigRule-', '')
  .replace('CR-', ''); // optional in case it's abbreviated

// Construct Lambda function name
const lambdaFnName = `${trimmedRuleName}-LambdaFn`;

// Optionally check length
if (lambdaFnName.length > 64) {
  throw new Error(`Lambda function name too long: ${lambdaFnName.length} chars`);
}

export const ruleName = originalRuleName;
export const automationLambdaFnName = lambdaFnName;
