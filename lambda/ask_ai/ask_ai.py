import json
import os
import urllib.error
import urllib.request
from datetime import datetime

import boto3


dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
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


def _extract_openai_text(response_body):
    if response_body.get("output_text"):
        return response_body["output_text"].strip()

    text_parts = []
    for item in response_body.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if text:
                text_parts.append(text)

    return "\n".join(text_parts).strip()


def _ask_openai(user_text):
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    request_body = {
        "model": OPENAI_MODEL,
        "instructions": AI_SYSTEM_PROMPT,
        "input": user_text,
        "max_output_tokens": 600,
    }

    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(request_body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            response_body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API error {e.code}: {error_body}") from e

    return _extract_openai_text(response_body) or "I could not generate a response."


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

        reply_text = _ask_openai(text)
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
                "AI is not available right now. Check that OPENAI_API_KEY is "
                "configured for the Lambda function and that the OpenAI model is available."
            ),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        try:
            _send_to_client(domain_name, stage, connection_id, error_payload)
        except Exception as send_error:
            print(f"Failed to send AI error to client: {send_error}")
        return {"statusCode": 500, "body": "Internal server error"}
