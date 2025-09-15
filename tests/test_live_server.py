#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试当前运行的服务器是否正确处理GLM-4.5-Search模型
"""

import asyncio
import json
import httpx
from app.core.config import settings

async def test_live_server():
    """测试实际运行的服务器"""
    
    print("🧪 测试当前运行的服务器...")
    print(f"服务器地址: http://localhost:{settings.LISTEN_PORT}")
    print()
    
    try:
        async with httpx.AsyncClient() as client:
            # 测试搜索模型请求
            search_request = {
                "model": "GLM-4.5-Search",
                "messages": [
                    {"role": "user", "content": "请搜索今天北京的天气"}
                ],
                "stream": True  # 使用流式以便观察日志
            }
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.AUTH_TOKEN}"
            }
            
            print(f"📤 发送GLM-4.5-Search请求...")
            print(f"请求内容: {json.dumps(search_request, ensure_ascii=False, indent=2)}")
            print()
            
            # 发送请求并接收流式响应
            async with client.stream(
                "POST",
                f"http://localhost:{settings.LISTEN_PORT}/v1/chat/completions",
                json=search_request,
                headers=headers,
                timeout=30.0
            ) as response:
                
                print(f"📥 响应状态: {response.status_code}")
                
                if response.status_code == 200:
                    print(f"✅ 请求成功，开始接收流式响应...")
                    print(f"💡 请查看服务器日志以确认是否正确添加了 deep-web-search MCP 服务器")
                    print()
                    
                    # 读取前几个响应块
                    chunk_count = 0
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            chunk_count += 1
                            if chunk_count <= 3:  # 只显示前3个块
                                data = line[6:]  # 去掉 "data: " 前缀
                                if data.strip() and data.strip() != "[DONE]":
                                    try:
                                        chunk_data = json.loads(data)
                                        content = chunk_data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                        if content:
                                            print(f"📦 响应块 {chunk_count}: {content}")
                                    except:
                                        pass
                            elif chunk_count > 10:  # 读取足够的块后停止
                                break
                    
                    print(f"\n✅ 流式响应正常，共接收 {chunk_count} 个数据块")
                    print(f"🔍 请检查服务器日志中是否包含以下信息:")
                    print(f"   - '模型特性检测: is_search=True'")
                    print(f"   - '🔍 检测到搜索模型，添加 deep-web-search MCP 服务器'")
                    print(f"   - 'MCP服务器列表: [\"deep-web-search\"]'")
                    
                else:
                    error_text = await response.aread()
                    print(f"❌ 请求失败: {response.status_code}")
                    print(f"错误信息: {error_text.decode('utf-8', errors='ignore')}")
                    
    except httpx.ConnectError:
        print(f"❌ 无法连接到服务器 localhost:{settings.LISTEN_PORT}")
        print(f"   请确保服务器正在运行: python main.py")
    except Exception as e:
        print(f"❌ 请求异常: {e}")

async def main():
    """主函数"""
    print("=" * 60)
    print("GLM-4.5-Search 实时服务器测试")
    print("=" * 60)
    print()
    
    await test_live_server()
    
    print()
    print("=" * 60)
    print("测试完成")
    print("=" * 60)
    print()
    print("📋 检查清单:")
    print("1. 服务器是否正常响应 GLM-4.5-Search 请求？")
    print("2. 日志中是否显示 'is_search=True'？")
    print("3. 日志中是否显示添加 deep-web-search MCP 服务器？")
    print("4. 如果以上信息缺失，请重启服务器以加载最新代码")

if __name__ == "__main__":
    asyncio.run(main())
