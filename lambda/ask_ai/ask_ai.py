import json
import os
import urllib.error
import urllib.request
from datetime import datetime

import boto3


dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
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


def _ask_ollama(user_text):
    request_body = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "messages": [
            {
                "role": "system",
                "content": AI_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_text,
            }
        ],
        "options": {
            "temperature": 0.6,
            "num_predict": 600,
        },
    }

    request = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/chat",
        data=json.dumps(request_body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            response_body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ollama API error {e.code}: {error_body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Ollama connection error: {e}") from e

    message = response_body.get("message", {})
    return message.get("content", "").strip() or "I could not generate a response."


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

        reply_text = _ask_ollama(text)
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
                "AI is not available right now. Check that OLLAMA_BASE_URL is reachable "
                "from the Lambda function and that the Ollama model is available."
            ),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        try:
            _send_to_client(domain_name, stage, connection_id, error_payload)
        except Exception as send_error:
            print(f"Failed to send AI error to client: {send_error}")
        return {"statusCode": 500, "body": "Internal server error"}
