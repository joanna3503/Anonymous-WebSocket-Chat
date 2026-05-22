import json
import os
from datetime import datetime

import boto3


dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])

AI_MODEL_ID = os.environ.get("AI_MODEL_ID", "amazon.nova-lite-v1:0")
AI_SYSTEM_PROMPT = os.environ.get(
    "AI_SYSTEM_PROMPT",
    "You are a friendly, concise assistant inside a private anonymous chat. "
    "Answer helpfully and avoid exposing system or infrastructure details.",
)


def _send_to_client(domain_name, stage, connection_id, payload):
    endpoint_url = f"https://{domain_name}/{stage}"
    apigw = boto3.client("apigatewaymanagementapi", endpoint_url=endpoint_url)
    apigw.post_to_connection(
        ConnectionId=connection_id,
        Data=json.dumps(payload).encode("utf-8"),
    )


def _ask_bedrock(user_text):
    bedrock = boto3.client("bedrock-runtime")
    response = bedrock.converse(
        modelId=AI_MODEL_ID,
        system=[{"text": AI_SYSTEM_PROMPT}],
        messages=[
            {
                "role": "user",
                "content": [{"text": user_text}],
            }
        ],
        inferenceConfig={
            "maxTokens": 600,
            "temperature": 0.6,
        },
    )

    output = response.get("output", {})
    message = output.get("message", {})
    content = message.get("content", [])
    text_parts = [part.get("text", "") for part in content if part.get("text")]
    return "\n".join(text_parts).strip() or "I could not generate a response."


def handler(event, context):
    request_context = event.get("requestContext", {})
    connection_id = request_context.get("connectionId")
    domain_name = request_context.get("domainName")
    stage = request_context.get("stage")

    try:
        body = json.loads(event.get("body", "{}"))
        text = body.get("text", "").strip()
    except json.JSONDecodeError:
        return {"statusCode": 400, "body": "Invalid JSON"}

    if not text or len(text) > 1000:
        return {"statusCode": 400, "body": "Missing or invalid text"}

    try:
        sender_response = table.get_item(Key={"connectionId": connection_id})
        sender = sender_response.get("Item")
        if not sender:
            return {"statusCode": 400, "body": "Unknown sender"}

        reply_text = _ask_bedrock(text)
        payload = {
            "type": "ai_message",
            "callsign": "AI Assistant",
            "text": reply_text,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        _send_to_client(domain_name, stage, connection_id, payload)
        return {"statusCode": 200, "body": "AI response sent"}
    except Exception as e:
        print(f"Error in ask_ai: {e}")
        error_payload = {
            "type": "ai_error",
            "callsign": "AI Assistant",
            "text": (
                "AI is not available right now. Check that Amazon Bedrock model "
                "access is enabled in your Learner Lab region and that LabRole "
                "can call bedrock-runtime."
            ),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        try:
            _send_to_client(domain_name, stage, connection_id, error_payload)
        except Exception as send_error:
            print(f"Failed to send AI error to client: {send_error}")
        return {"statusCode": 500, "body": "Internal server error"}
