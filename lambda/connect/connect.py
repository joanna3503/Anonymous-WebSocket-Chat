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
        
        # --- Broadcast 'user_joined' system message ---
        domain_name = request_context.get('domainName')
        stage = request_context.get('stage')
        
        if domain_name and stage:
            endpoint_url = f"https://{domain_name}/{stage}"
            apigw = boto3.client('apigatewaymanagementapi', endpoint_url=endpoint_url)
            
            payload = {
                "type": "system",
                "callsign": callsign,
                "event": "user_joined",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
            # Retrieve all active connections
            connections_response = table.scan(ProjectionExpression="connectionId")
            connections = connections_response.get('Items', [])
            
            for conn in connections:
                target_id = conn['connectionId']
                # Do not send the notification to the user who just joined
                if target_id != connection_id:
                    try:
                        apigw.post_to_connection(
                            ConnectionId=target_id,
                            Data=json.dumps(payload).encode('utf-8')
                        )
                    except apigw.exceptions.GoneException:
                        # Clean up stale connections
                        table.delete_item(Key={'connectionId': target_id})
                    except Exception as e:
                        print(f"Failed to send to {target_id}: {e}")
                        
        return {'statusCode': 200, 'body': 'Connected'}
    except Exception as e:
        print(f"Error saving connection: {e}")
        return {'statusCode': 500, 'body': 'Internal server error'}