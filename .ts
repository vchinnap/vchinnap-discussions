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
