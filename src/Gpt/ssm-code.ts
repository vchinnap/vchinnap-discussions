const customDocument = new ssm.CfnDocument(this, 'CustomConfigNotification', {
    content: {
        schemaVersion: '0.3',
        description: 'Custom notification for AWS Config non-compliance',
        parameters: {
            AutomationAssumeRole: { type: 'String' },
            TopicArn: { type: 'String' },
            resourceId: { type: 'String' },
            resourceType: { type: 'String' },
            complianceType: { type: 'String' },
            accountId: { type: 'String' },
            awsRegion: { type: 'String' },
            configRuleName: { type: 'String' },
            annotation: { type: 'String' },
        },
        mainSteps: [
            {
                name: 'ConstructMessage',
                action: 'aws:executeScript',
                inputs: {
                    Runtime: 'python3.8',
                    Handler: 'handler',
                    Script: `
def handler(event, context):
    msg = """AWS Config non-compliant resource.
ResourceId: {resourceId}
ResourceType: {resourceType}
ComplianceType: {complianceType}
AWS Account ID: {accountId}
AWS Region: {awsRegion}
Config Rule Name: {configRuleName}
Details: {annotation}""".format(**event)
    return {"message": msg}
                    `.trim(),
                    InputPayload: {
                        resourceId: '{{ resourceId }}',
                        resourceType: '{{ resourceType }}',
                        complianceType: '{{ complianceType }}',
                        accountId: '{{ accountId }}',
                        awsRegion: '{{ awsRegion }}',
                        configRuleName: '{{ configRuleName }}',
                        annotation: '{{ annotation }}',
                    },
                },
                outputs: [
                    {
                        Name: 'message',
                        Selector: '$.Payload.message',
                        Type: 'String',
                    },
                ],
            },
            {
                name: 'PublishToSNS',
                action: 'aws:executeAwsApi',
                inputs: {
                    Service: 'sns',
                    Api: 'Publish',
                    TopicArn: '{{ TopicArn }}',
                    Message: '{{ ConstructMessage.message }}',
                },
            },
        ],
    },
    documentType: 'Automation',
    name: 'CustomConfigNotification',
});
