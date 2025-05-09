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
