import os
import json
from datetime import datetime
import boto3

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])

def handler(event, context):
    """
    Receives a chat message, retrieves the sender's callsign,
    and broadcasts the message to all connected clients.
    """
    request_context = event.get('requestContext', {})
    connection_id = request_context.get('connectionId')
    domain_name = request_context.get('domainName')
    stage = request_context.get('stage')
    
    try:
        body = json.loads(event.get('body', '{}'))
        text = body.get('text', '')
    except json.JSONDecodeError:
        return {'statusCode': 400, 'body': 'Invalid JSON'}
        
    if not text or len(text) > 1000:
        return {'statusCode': 400, 'body': 'Missing or invalid text'}

    try:
        # Get sender's callsign from DynamoDB
        response = table.get_item(Key={'connectionId': connection_id})
        sender = response.get('Item')
        if not sender:
            return {'statusCode': 400, 'body': 'Unknown sender'}
            
        callsign = sender['callsign']
        
        # Build broadcast payload
        payload = {
            "type": "message",
            "callsign": callsign,
            "text": text,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        # Initialize API Gateway Management API client
        endpoint_url = f"https://{domain_name}/{stage}"
        apigw = boto3.client('apigatewaymanagementapi', endpoint_url=endpoint_url)
        
        # Scan for all connections
        connections_response = table.scan(ProjectionExpression="connectionId")
        connections = connections_response.get('Items', [])
        
        # Fan-out message to all connections
        for conn in connections:
            target_id = conn['connectionId']
            try:
                apigw.post_to_connection(
                    ConnectionId=target_id,
                    Data=json.dumps(payload).encode('utf-8')
                )
            except apigw.exceptions.GoneException:
                # Clean up stale connection
                table.delete_item(Key={'connectionId': target_id})
            except Exception as e:
                print(f"Failed to send to {target_id}: {e}")
                
        return {'statusCode': 200, 'body': 'Message sent'}
    except Exception as e:
        print(f"Error in send_message: {e}")
        return {'statusCode': 500, 'body': 'Internal server error'}