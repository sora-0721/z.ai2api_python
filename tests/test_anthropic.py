# -*- coding: utf-8 -*-

import json
import requests

# 服务器配置
BASE_URL = "http://localhost:8080/v1/messages"
API_KEY = "sk-your-api-key"  # 修改为你的 API key

test_data = {
    "model": "GLM-4.5",
    "messages": [
        {
            "role": "user",
            "content": "你好，这是一个测试"
        }
    ],
    "system": [
        {
            "type": "text",
            "text": "You are Claude Code, Anthropic's official CLI for Claude.",
            "cache_control": {
                "type": "ephemeral"
            }
        }
    ],
    "max_tokens": 1024,
    "stream": False,
}

def test_non_stream():
    """测试非流式请求"""
    print("=== 测试非流式请求 ===")
    
    try:
        response = requests.post(
            BASE_URL,
            headers={"x-api-key": API_KEY},
            json=test_data,
            timeout=30.0
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("响应成功!")
            print(f"ID: {result.get('id')}")
            print(f"模型: {result.get('model')}")
            if result.get('content'):
                print(f"内容: {result['content'][0]['text']}")
        else:
            print("错误响应:")
            print(response.text)
            
    except Exception as e:
        print(f"请求失败: {e}")

def test_stream():
    """测试流式请求"""
    print("\n=== 测试流式请求 ===")
    
    stream_data = test_data.copy()
    stream_data["stream"] = True
    
    try:
        response = requests.post(
            BASE_URL,
            headers={"x-api-key": API_KEY},
            json=stream_data,
            stream=True,
            timeout=30.0
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            print("流式响应内容:")
            for line in response.iter_lines():
                if line:
                    print(f"  {line.decode('utf-8')}")
        else:
            print("错误响应:")
            print(response.text)
            
    except Exception as e:
        print(f"请求失败: {e}")

if __name__ == "__main__":
    try:
        test_non_stream()
        test_stream()
    except KeyboardInterrupt:
        print("\n测试已取消")