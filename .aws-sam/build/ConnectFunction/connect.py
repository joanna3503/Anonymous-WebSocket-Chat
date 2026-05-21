import os
import json
from datetime import datetime
import boto3

# Initialize DynamoDB resource
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])

def handler(event, context):
    """
    Handles new WebSocket connections.
    Stores the connectionId and user callsign in DynamoDB.
    """
    request_context = event.get('requestContext', {})
    connection_id = request_context.get('connectionId')
    
    query_params = event.get('queryStringParameters', {})
    callsign = query_params.get('callsign')
    
    # Return 400 if callsign is missing or invalid
    if not callsign or not isinstance(callsign, str) or len(callsign) > 20:
        return {
            'statusCode': 400,
            'body': 'Invalid or missing callsign'
        }
        
    try:
        # Write connection item to DynamoDB
        table.put_item(
            Item={
                'connectionId': connection_id,
                'callsign': callsign,
                'connectedAt': datetime.utcnow().isoformat() + "Z"
            }
        )
        return {'statusCode': 200, 'body': 'Connected'}
    except Exception as e:
        print(f"Error saving connection: {e}")
        return {'statusCode': 500, 'body': 'Internal server error'}