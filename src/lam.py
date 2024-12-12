import json

def lambda_handler(event, context):
    print(f"Received event: {json.dumps(event)}")  # Log the full event for debugging

    # Parse the 'invokingEvent' field from the event
    invoking_event = json.loads(event.get('invokingEvent', '{}'))
    
    # Ensure 'configurationItem' exists in the parsed 'invokingEvent'
    config = invoking_event.get('configurationItem')
    if not config:
        raise ValueError("The 'configurationItem' is missing in the invoking event")

    # Extract the 'resourceId' from 'configurationItem'
    instance_id = config.get('resourceId')
    if not instance_id:
        raise ValueError("InstanceID is missing in the configurationItem")

    print(f"Extracted instance ID: {instance_id}")
    
    # Proceed with compliance evaluation
    compliance = evaluate_compliance(instance_id)
    
    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Compliance evaluated successfully",
            "compliance": compliance
        }),
    }
