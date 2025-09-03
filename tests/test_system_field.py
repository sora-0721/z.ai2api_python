#!/usr/bin/env python3
"""
测试 Anthropic API system 字段数组类型支持
"""
import json
import requests

# 测试数据
test_cases = [
    {
        "name": "字符串类型 system",
        "data": {
            "model": "GLM-4.5",
            "messages": [{"role": "user", "content": "你好"}],
            "system": "你是一个有帮助的助手",
            "max_tokens": 100
        }
    },
    {
        "name": "数组类型 system",
        "data": {
            "model": "GLM-4.5",
            "messages": [{"role": "user", "content": "你好"}],
            "system": [
                {
                    "type": "text",
                    "text": "你是一个有帮助的助手",
                    "cache_control": {"type": "ephemeral"}
                }
            ],
            "max_tokens": 100
        }
    }
]

def test_system_field():
    """测试 system 字段的不同格式"""
    print("=== 测试 system 字段支持 ===\n")
    
    for test_case in test_cases:
        print(f"测试: {test_case['name']}")
        
        try:
            response = requests.post(
                "http://localhost:8080/v1/messages",
                headers={"x-api-key": "sk-your-api-key"},
                json=test_case["data"],
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                print("✅ 成功")
                print(f"   消息ID: {result.get('id')}")
                print(f"   内容预览: {result['content'][0]['text'][:50]}...")
            else:
                print(f"❌ 失败 - 状态码: {response.status_code}")
                print(f"   错误: {response.text}")
                
        except Exception as e:
            print(f"❌ 异常: {e}")
        
        print()

if __name__ == "__main__":
    print("请确保服务器正在运行在 http://localhost:8080")
    input("按 Enter 开始测试...")
    test_system_field()