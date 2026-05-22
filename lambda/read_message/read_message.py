import os
import json
import boto3

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])

def handler(event, context):
    request_context = event.get('requestContext', {})
    connection_id = request_context.get('connectionId')
    domain_name = request_context.get('domainName')
    stage = request_context.get('stage')

    try:
        body = json.loads(event.get('body', '{}'))
        message_id = body.get('messageId')
    except json.JSONDecodeError:
        return {'statusCode': 400, 'body': 'Invalid JSON'}

    if not message_id:
        return {'statusCode': 400, 'body': 'Missing messageId'}

    try:
        # Get reader's callsign from DynamoDB
        response = table.get_item(Key={'connectionId': connection_id})
        reader = response.get('Item')
        if not reader:
            return {'statusCode': 400, 'body': 'Unknown user'}

        reader_callsign = reader['callsign']

        # Create "read receipt" payload
        payload = {
            "type": "read_receipt",
            "messageId": message_id,
            "reader": reader_callsign
        }

        endpoint_url = f"https://{domain_name}/{stage}"
        apigw = boto3.client('apigatewaymanagementapi', endpoint_url=endpoint_url)

        # Broadcast "read receipt" to all connected clients
        connections_response = table.scan(ProjectionExpression="connectionId")
        for conn in connections_response.get('Items', []):
            target_id = conn['connectionId']
            try:
                apigw.post_to_connection(
                    ConnectionId=target_id,
                    Data=json.dumps(payload).encode('utf-8')
                )
            except apigw.exceptions.GoneException:
                table.delete_item(Key={'connectionId': target_id})
            except Exception as e:
                print(f"Failed to send read receipt to {target_id}: {e}")

        return {'statusCode': 200, 'body': 'Read receipt broadcasted'}
    except Exception as e:
        print(f"Error in read_message: {e}")
        return {'statusCode': 500, 'body': 'Internal server error'}