import json
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import request
from urllib.error import HTTPError, URLError


AGENT_CARD_PATH = "/.well-known/agent-card.json"


def text_message(text, context_id=None, message_id=None):
    message = {
        "kind": "message",
        "messageId": message_id or str(uuid.uuid4()),
        "role": "agent",
        "parts": [{"kind": "text", "text": text}],
    }

    if context_id:
        message["contextId"] = context_id

    return message


def jsonrpc_result(request_id, result):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result,
    }


def jsonrpc_error(request_id, code, message):
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def extract_text(message):
    for part in message.get("parts", []):
        if part.get("kind") == "text":
            return part.get("text", "")
    return ""


class A2ARequestHandler(BaseHTTPRequestHandler):
    agent_card = None
    message_handler = None

    def _send_json(self, status_code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return

    def do_GET(self):
        if self.path == AGENT_CARD_PATH:
            self._send_json(200, self.agent_card)
            return

        self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json(400, jsonrpc_error(None, -32700, "Parse error"))
            return

        method = payload.get("method")
        request_id = payload.get("id")

        if method != "message/send":
            self._send_json(400, jsonrpc_error(request_id, -32601, "Method not found"))
            return

        params = payload.get("params", {})
        message = params.get("message", {})
        context_id = message.get("contextId")
        user_text = extract_text(message)

        try:
            response_text = self.message_handler(user_text)
        except Exception as exc:
            self._send_json(500, jsonrpc_error(request_id, -32000, f"Agent execution error: {exc}"))
            return

        result = {
            "kind": "message",
            "message": text_message(response_text, context_id=context_id),
        }
        self._send_json(200, jsonrpc_result(request_id, result))


def make_agent_handler(agent_card, message_handler):
    class CustomHandler(A2ARequestHandler):
        pass

    CustomHandler.agent_card = agent_card
    CustomHandler.message_handler = staticmethod(message_handler)
    return CustomHandler


def run_a2a_server(host, port, agent_card, message_handler):
    handler = make_agent_handler(agent_card, message_handler)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Serving {agent_card['name']} at http://{host}:{port}")
    server.serve_forever()


def fetch_agent_card(base_url):
    url = f"{base_url.rstrip('/')}{AGENT_CARD_PATH}"
    with request.urlopen(url) as response:
        return json.loads(response.read().decode("utf-8"))


def send_message(base_url, text):
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/send",
        "params": {
            "message": {
                "kind": "message",
                "messageId": str(uuid.uuid4()),
                "role": "user",
                "parts": [{"kind": "text", "text": text}],
            }
        },
    }

    data = json.dumps(payload).encode("utf-8")
    http_request = request.Request(
        base_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(http_request) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8")
        raise RuntimeError(f"HTTP {exc.code}: {error_body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error: {exc}") from exc

    if "error" in body:
        raise RuntimeError(body["error"]["message"])

    return extract_text(body["result"]["message"])
