#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试修复后的工具调用功能
"""

import json
import asyncio
import httpx
from typing import Dict, Any

# 测试配置
TEST_URL = "http://localhost:8080/v1/chat/completions"
TEST_AUTH_TOKEN = "sk-test-key"

# 测试工具定义
TEST_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取指定城市的天气信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称"
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "温度单位"
                    }
                },
                "required": ["city"]
            }
        }
    }
]

async def test_tool_call_streaming():
    """测试流式工具调用"""
    print("🧪 开始测试流式工具调用...")
    
    payload = {
        "model": "glm-4.5",
        "messages": [
            {
                "role": "user", 
                "content": "请帮我查询北京的天气，使用摄氏度"
            }
        ],
        "tools": TEST_TOOLS,
        "stream": True,
        "temperature": 0.7
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TEST_AUTH_TOKEN}"
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream(
                "POST", 
                TEST_URL, 
                json=payload, 
                headers=headers
            ) as response:
                print(f"📡 响应状态: {response.status_code}")
                print(f"📡 响应头: {dict(response.headers)}")
                
                if response.status_code != 200:
                    error_text = await response.aread()
                    print(f"❌ 请求失败: {error_text.decode()}")
                    return
                
                print("\n📦 开始接收流式数据:")
                print("-" * 80)
                
                chunk_count = 0
                tool_calls_found = False
                
                async for line in response.aiter_lines():
                    if not line:
                        continue
                        
                    if line.startswith("data: "):
                        chunk_count += 1
                        data_str = line[6:].strip()
                        
                        if data_str == "[DONE]":
                            print(f"🏁 [{chunk_count:03d}] 流结束: [DONE]")
                            break
                            
                        try:
                            chunk = json.loads(data_str)
                            
                            # 检查是否包含工具调用
                            choices = chunk.get("choices", [])
                            if choices:
                                choice = choices[0]
                                delta = choice.get("delta", {})
                                tool_calls = delta.get("tool_calls", [])
                                
                                if tool_calls:
                                    tool_calls_found = True
                                    print(f"🔧 [{chunk_count:03d}] 工具调用块:")
                                    for tool_call in tool_calls:
                                        print(f"    ID: {tool_call.get('id', 'N/A')}")
                                        print(f"    类型: {tool_call.get('type', 'N/A')}")
                                        function = tool_call.get('function', {})
                                        print(f"    函数名: {function.get('name', 'N/A')}")
                                        print(f"    参数: {function.get('arguments', 'N/A')}")
                                        print(f"    参数类型: {type(function.get('arguments', 'N/A'))}")
                                
                                finish_reason = choice.get("finish_reason")
                                if finish_reason:
                                    print(f"🏁 [{chunk_count:03d}] 完成原因: {finish_reason}")
                                
                                # 显示其他内容
                                content = delta.get("content")
                                if content:
                                    print(f"💬 [{chunk_count:03d}] 内容: {content}")
                            
                            # 显示usage信息
                            usage = chunk.get("usage")
                            if usage:
                                print(f"📊 [{chunk_count:03d}] 使用统计: {usage}")
                                
                        except json.JSONDecodeError as e:
                            print(f"❌ [{chunk_count:03d}] JSON解析错误: {e}")
                            print(f"    原始数据: {data_str[:200]}...")
                
                print("-" * 80)
                print(f"✅ 测试完成，共处理 {chunk_count} 个数据块")
                print(f"🔧 工具调用检测: {'成功' if tool_calls_found else '失败'}")
                
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()

async def test_tool_call_non_streaming():
    """测试非流式工具调用"""
    print("\n🧪 开始测试非流式工具调用...")
    
    payload = {
        "model": "glm-4.5",
        "messages": [
            {
                "role": "user", 
                "content": "请帮我查询上海的天气"
            }
        ],
        "tools": TEST_TOOLS,
        "stream": False,
        "temperature": 0.7
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TEST_AUTH_TOKEN}"
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(TEST_URL, json=payload, headers=headers)
            
            print(f"📡 响应状态: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print("📦 响应结果:")
                print(json.dumps(result, indent=2, ensure_ascii=False))
                
                # 检查工具调用
                choices = result.get("choices", [])
                if choices:
                    message = choices[0].get("message", {})
                    tool_calls = message.get("tool_calls", [])
                    if tool_calls:
                        print(f"🔧 发现 {len(tool_calls)} 个工具调用")
                        for i, tool_call in enumerate(tool_calls):
                            print(f"  工具 {i+1}: {tool_call}")
                    else:
                        print("❌ 未发现工具调用")
            else:
                print(f"❌ 请求失败: {response.text}")
                
    except Exception as e:
        print(f"❌ 测试异常: {e}")

async def main():
    """主测试函数"""
    print("🚀 开始工具调用修复验证测试")
    print("=" * 80)
    
    # 测试流式工具调用
    await test_tool_call_streaming()
    
    # 等待一下
    await asyncio.sleep(2)
    
    # 测试非流式工具调用
    await test_tool_call_non_streaming()
    
    print("\n" + "=" * 80)
    print("🎯 测试完成")

if __name__ == "__main__":
    asyncio.run(main())
