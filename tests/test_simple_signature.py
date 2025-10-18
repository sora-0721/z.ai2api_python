import time, hmac, hashlib, requests, uuid, json, base64

token = ""

def decode_jwt_payload(token):
    parts = token.split('.')
    payload = parts[1]
    padding = 4 - len(payload) % 4
    if padding != 4:
        payload += '=' * padding
    decoded = base64.urlsafe_b64decode(payload)
    return json.loads(decoded)

def zs(e, t, timestamp):
    r = str(timestamp)
    t_encoded = base64.b64encode(t.encode('utf-8')).decode('utf-8')
    i = f"{e}|{t_encoded}|{r}"

    n = timestamp // (5 * 60 * 1000)
    key = "junjie".encode('utf-8')
    o = hmac.new(key, str(n).encode('utf-8'), hashlib.sha256).hexdigest()
    signature = hmac.new(o.encode('utf-8'), i.encode('utf-8'), hashlib.sha256).hexdigest()

    return {"signature": signature, "timestamp": timestamp}

# 使用最小参数测试
payload_jwt = decode_jwt_payload(token)
user_id = payload_jwt['id']
chat_id = str(uuid.uuid4())
timestamp = int(time.time() * 1000)
request_id = str(uuid.uuid4())
message = "hello"

# Generate signature
e = f"requestId,{request_id},timestamp,{timestamp},user_id,{user_id}"
result = zs(e, message, timestamp)
signature = result["signature"]

print(f"Timestamp: {timestamp}")
print(f"Request ID: {request_id}")
print(f"Signature: {signature}")
print()

# 最小化 URL 参数
from urllib.parse import urlencode
params = {
    "timestamp": str(timestamp),
    "requestId": request_id,
    "user_id": user_id,
    "token": token,
    "version": "0.0.1",
    "platform": "web",
}

base_url = "https://chat.z.ai/api/chat/completions"
url_params = urlencode(params)
url = f"{base_url}?{url_params}&signature_timestamp={timestamp}"

headers = {
    "Authorization": f"Bearer {token}",
    "X-Signature": signature,
    "Content-Type": "application/json"
}

body_payload = {
    "signature_prompt": message,
    "stream": False,
    "model": "GLM-4-6-API-V1",
    "messages": [{"role": "user", "content": message}],
    "chat_id": chat_id,
    "id": str(uuid.uuid4())
}

print(f"URL: {url}")
print(f"Headers: {json.dumps(headers, indent=2)}")
print(f"Body: {json.dumps(body_payload, indent=2)}")
print()

response = requests.post(url, headers=headers, json=body_payload)
print(f"Status: {response.status_code}")
print(f"Response: {response.text}")
