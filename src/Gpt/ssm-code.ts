import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as cr from 'aws-cdk-lib/custom-resources';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

export class MyLambdaStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Step 1: Create the Lambda Function
    const myFunction = new lambda.Function(this, 'MyLambdaFunction', {
      runtime: lambda.Runtime.NODEJS_18_X,
      handler: 'index.handler',
      code: lambda.Code.fromAsset('lambda'), // Folder containing your Lambda code
    });

    // Step 2: Define the AWS SDK call to invoke the Lambda function
    const lambdaInvocation = {
      service: 'Lambda',
      action: 'invoke',
      parameters: {
        FunctionName: myFunction.functionName,
        InvocationType: 'Event',
        Payload: JSON.stringify({ key: 'value' }),
      },
      physicalResourceId: cr.PhysicalResourceId.of(Date.now().toString()), // Ensures a new invocation on each deployment
    };

    // Step 3: Create the Custom Resource to invoke the Lambda function on deployment
    const lambdaTrigger = new cr.AwsCustomResource(this, 'InvokeLambdaOnDeploy', {
      onCreate: lambdaInvocation,
      onUpdate: lambdaInvocation,
      policy: cr.AwsCustomResourcePolicy.fromSdkCalls({ resources: [myFunction.functionArn] }),
    });

    // Ensure the custom resource is created after the Lambda function
    lambdaTrigger.node.addDependency(myFunction);
  }
}
