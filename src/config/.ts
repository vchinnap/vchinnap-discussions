import * as fs from 'fs';
import * as path from 'path';

const documentContent = JSON.parse(
  fs.readFileSync(
    path.resolve(__dirname, '../../../service/remediations/evaluation-ssm-content.json'),
    'utf8'
  )
);


import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import { Tags } from 'aws-cdk-lib';

const eventRule = new events.Rule(this, `${ruleName}-LambdaTagUpdateTrigger`, {
  eventPattern: {
    source: ['aws.lambda'],
    detailType: ['AWS API Call via CloudTrail'],
    detail: {
      eventSource: ['lambda.amazonaws.com'],
      eventName: [
        'CreateFunction20150331',
        'UpdateFunctionConfiguration20150331'
      ],
      requestParameters: {
        functionName: [functionRuleName]  // your tagging Lambda name
      }
    }
  },
  targets: [new targets.LambdaFunction(this.taggingLambda.lambdaFunction)]
});

// ✅ Apply your tags
for (const [key, value] of Object.entries(tags)) {
  Tags.of(eventRule).add(key, value);
}



/**
 * ╔══════════════════════════════════════════════╗
 * ║              CONFIG RULE LOGIC              ║
 * ╚══════════════════════════════════════════════╝
 */

/**
 * 🟧 EVALUATION PART
 * ------------------------------------------------
 * - This section evaluates the AWS resource's state.
 * - Example: Checks if a specific tag ('start') is set to 'enabled'.
 * - Based on this, it returns COMPLIANT or NON_COMPLIANT.
 */
function evaluateCompliance(configItem: any): 'COMPLIANT' | 'NON_COMPLIANT' {
  const tags = configItem.configuration?.tags || {};
  const startTag = tags['start']?.toLowerCase();

  return startTag === 'enabled' ? 'COMPLIANT' : 'NON_COMPLIANT';
}

/**
 * 🟦 REMEDIATION PART
 * ------------------------------------------------
 * - If the evaluation result is NON_COMPLIANT,
 *   this section takes corrective action.
 * - Example: Starts the EC2 instance using AWS SDK.
 */
async function remediateInstance(instanceId: string): Promise<void> {
  const ec2 = new AWS.EC2();
  await ec2.startInstances({ InstanceIds: [instanceId] }).promise();
  console.log(`Remediation: Started instance ${instanceId}`);
}
