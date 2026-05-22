import os
import json
from datetime import datetime
import boto3

# Initialize DynamoDB resource
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])

def handler(event, context):
    """
    Handles WebSocket disconnections.
    Removes the connectionId from DynamoDB.
    """
    request_context = event.get('requestContext', {})
    connection_id = request_context.get('connectionId')
    
    try:
        # 1. Retrieve user details before deleting to get the callsign
        response = table.get_item(Key={'connectionId': connection_id})
        user = response.get('Item')
        callsign = user.get('callsign') if user else "Someone"

        # 2. Delete item from DynamoDB
        table.delete_item(
            Key={'connectionId': connection_id}
        )
        
        # 3. Broadcast 'user_left' system message
        domain_name = request_context.get('domainName')
        stage = request_context.get('stage')
        
        # Only broadcast if we successfully identified the disconnected user
        if domain_name and stage and user:
            endpoint_url = f"https://{domain_name}/{stage}"
            apigw = boto3.client('apigatewaymanagementapi', endpoint_url=endpoint_url)
            
            payload = {
                "type": "system",
                "callsign": callsign,
                "event": "user_left",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
            # Retrieve remaining active connections
            connections_response = table.scan(ProjectionExpression="connectionId")
            connections = connections_response.get('Items', [])
            
            for conn in connections:
                target_id = conn['connectionId']
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

        return {'statusCode': 200, 'body': 'Disconnected'}
    except Exception as e:
        print(f"Error deleting connection: {e}")
        return {'statusCode': 500, 'body': 'Internal server error'}