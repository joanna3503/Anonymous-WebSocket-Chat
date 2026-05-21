import os
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
        # Delete item from DynamoDB (Idempotent operation)
        table.delete_item(
            Key={'connectionId': connection_id}
        )
        return {'statusCode': 200, 'body': 'Disconnected'}
    except Exception as e:
        print(f"Error deleting connection: {e}")
        return {'statusCode': 500, 'body': 'Internal server error'}