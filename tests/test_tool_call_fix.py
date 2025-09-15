#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试工具调用
"""

import json
import urllib.request
import urllib.parse
from typing import Dict, Any

def test_tool_call():
    """测试工具调用功能"""

    # 测试请求
    test_request = {
        "model": "glm-4.5",
        "messages": [
            {
                "role": "user",
                "content": "请打开Google网站"
            }
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "playwri-browser_navigate",
                    "description": "Navigate to a URL in the browser",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "The URL to navigate to"
                            }
                        },
                        "required": ["url"]
                    }
                }
            }
        ],
        "stream": True
    }

    print("🚀 发送工具调用测试请求...")
    print(f"📦 请求内容: {json.dumps(test_request, ensure_ascii=False, indent=2)}")

    # 准备HTTP请求
    url = "http://localhost:8080/v1/chat/completions"
    data = json.dumps(test_request).encode('utf-8')

    req = urllib.request.Request(url, data=data)
    req.add_header('Content-Type', 'application/json')
    req.add_header('Authorization', 'Bearer sk-test-key')

    try:
        with urllib.request.urlopen(req) as response:
            print(f"📈 响应状态: {response.status}")

            if response.status == 200:
                print("✅ 开始接收流式响应...")

                tool_calls_found = []
                chunk_count = 0

                for line in response:
                    line = line.decode('utf-8').strip()
                    if line.startswith('data: '):
                        chunk_count += 1
                        data_str = line[6:]  # 去掉 'data: ' 前缀

                        if data_str == '[DONE]':
                            print("🏁 接收到结束信号")
                            break

                        try:
                            chunk = json.loads(data_str)

                            # 检查是否包含工具调用
                            if 'choices' in chunk and chunk['choices']:
                                choice = chunk['choices'][0]
                                if 'delta' in choice and 'tool_calls' in choice['delta']:
                                    tool_calls = choice['delta']['tool_calls']
                                    if tool_calls:
                                        for tool_call in tool_calls:
                                            print(f"🔧 发现工具调用: {json.dumps(tool_call, ensure_ascii=False, indent=2)}")
                                            tool_calls_found.append(tool_call)

                                # 检查完成原因
                                if choice.get('finish_reason') == 'tool_calls':
                                    print("✅ 工具调用完成")

                        except json.JSONDecodeError as e:
                            print(f"❌ JSON解析错误: {e}, 数据: {data_str[:200]}")

                print(f"📊 总共接收到 {chunk_count} 个数据块")
                print(f"🔧 发现 {len(tool_calls_found)} 个工具调用")

                # 分析工具调用格式
                for i, tool_call in enumerate(tool_calls_found):
                    print(f"\n🔍 工具调用 {i+1} 分析:")
                    print(f"  ID: {tool_call.get('id', 'N/A')}")
                    print(f"  类型: {tool_call.get('type', 'N/A')}")

                    if 'function' in tool_call:
                        func = tool_call['function']
                        print(f"  函数名: {func.get('name', 'N/A')}")

                        arguments = func.get('arguments', '')
                        print(f"  参数类型: {type(arguments)}")
                        print(f"  参数内容: {arguments}")

                        # 尝试解析参数
                        if isinstance(arguments, str) and arguments:
                            try:
                                parsed_args = json.loads(arguments)
                                print(f"  ✅ 参数解析成功: {parsed_args}")
                            except json.JSONDecodeError as e:
                                print(f"  ❌ 参数解析失败: {e}")
                        elif isinstance(arguments, dict):
                            print(f"  ⚠️  参数是对象格式（应该是字符串）: {arguments}")

            else:
                error_text = response.read().decode('utf-8')
                print(f"❌ 请求失败: {error_text}")

    except Exception as e:
        print(f"❌ 请求异常: {e}")

if __name__ == "__main__":
    test_tool_call()
