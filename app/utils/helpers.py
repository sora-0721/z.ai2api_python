"""
Utility functions for the application
"""

import json
import re
import time
from typing import Dict, List, Optional, Any, Tuple, Generator
import requests

from app.core.config import settings


def debug_log(message: str, *args) -> None:
    """Log debug message if debug mode is enabled"""
    if settings.DEBUG_LOGGING:
        if args:
            print(f"[DEBUG] {message % args}")
        else:
            print(f"[DEBUG] {message}")


def generate_request_ids() -> Tuple[str, str]:
    """Generate unique IDs for chat and message"""
    timestamp = int(time.time())
    chat_id = f"{timestamp * 1000}-{timestamp}"
    msg_id = str(timestamp * 1000000)
    return chat_id, msg_id


def get_browser_headers(referer_chat_id: str = "") -> Dict[str, str]:
    """Get browser headers for API requests"""
    headers = settings.CLIENT_HEADERS.copy()
    
    if referer_chat_id:
        headers["Referer"] = f"{settings.CLIENT_HEADERS['Origin']}/c/{referer_chat_id}"
    
    return headers


def get_anonymous_token() -> str:
    """Get anonymous token for authentication"""
    headers = get_browser_headers()
    headers.update({
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": f"{settings.CLIENT_HEADERS['Origin']}/",
    })
    
    try:
        response = requests.get(
            f"{settings.CLIENT_HEADERS['Origin']}/api/v1/auths/",
            headers=headers,
            timeout=10.0
        )
        
        if response.status_code != 200:
            raise Exception(f"anon token status={response.status_code}")
        
        data = response.json()
        token = data.get("token")
        if not token:
            raise Exception("anon token empty")
        
        return token
    except Exception as e:
        debug_log(f"获取匿名token失败: {e}")
        raise


def get_auth_token() -> str:
    """Get authentication token (anonymous or fixed)"""
    if settings.ANONYMOUS_MODE:
        try:
            token = get_anonymous_token()
            debug_log(f"匿名token获取成功: {token[:10]}...")
            return token
        except Exception as e:
            debug_log(f"匿名token获取失败，回退固定token: {e}")
    
    return settings.BACKUP_TOKEN


def transform_thinking_content(content: str) -> str:
    """Transform thinking content according to configuration"""
    # Remove summary tags
    content = re.sub(r'(?s)<summary>.*?</summary>', '', content)
    # Clean up remaining tags
    content = content.replace("</thinking>", "").replace("<Full>", "").replace("</Full>", "")
    content = content.strip()
    
    if settings.THINKING_PROCESSING == "think":
        content = re.sub(r'<details[^>]*>', '<span>', content)
        content = content.replace("</details>", "</span>")
    elif settings.THINKING_PROCESSING == "strip":
        content = re.sub(r'<details[^>]*>', '', content)
        content = content.replace("</details>", "")
    
    # Remove line prefixes
    content = content.lstrip("> ")
    content = content.replace("\n> ", "\n")
    
    return content.strip()


def call_upstream_api(
    upstream_req: Any,
    chat_id: str,
    auth_token: str
) -> requests.Response:
    """Call upstream API with proper headers"""
    headers = get_browser_headers(chat_id)
    headers["Authorization"] = f"Bearer {auth_token}"
    
    debug_log(f"调用上游API: {settings.API_ENDPOINT}")
    debug_log(f"上游请求体: {upstream_req.model_dump_json()}")
    
    response = requests.post(
        settings.API_ENDPOINT,
        json=upstream_req.model_dump(exclude_none=True),
        headers=headers,
        timeout=60.0,
        stream=True
    )
    
    debug_log(f"上游响应状态: {response.status_code}")
    return response