#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
对比不同模型的搜索行为
"""

import asyncio
import json
import httpx
from app.core.config import settings

async def test_model(model_name: str, question: str):
    """测试特定模型的响应"""
    
    print(f"🧪 测试模型: {model_name}")
    print(f"问题: {question}")
    print()
    
    try:
        async with httpx.AsyncClient() as client:
            request_data = {
                "model": model_name,
                "messages": [
                    {"role": "user", "content": question}
                ],
                "stream": False  # 使用非流式以便完整查看响应
            }
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.AUTH_TOKEN}"
            }
            
            response = await client.post(
                f"http://localhost:{settings.LISTEN_PORT}/v1/chat/completions",
                json=request_data,
                headers=headers,
                timeout=60.0
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                print(f"✅ 响应成功:")
                print(f"内容: {content[:200]}...")
                print()
                
                # 检查是否包含搜索相关的内容
                search_indicators = [
                    "搜索", "查询", "实时", "最新", "网络", "互联网",
                    "search", "query", "real-time", "latest", "web", "internet"
                ]
                
                has_search_content = any(indicator in content.lower() for indicator in search_indicators)
                if has_search_content:
                    print(f"🔍 检测到搜索相关内容")
                else:
                    print(f"❌ 未检测到搜索相关内容")
                
                return content
            else:
                print(f"❌ 请求失败: {response.status_code}")
                print(f"错误: {response.text}")
                return None
                
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return None

async def main():
    """主测试函数"""
    print("=" * 80)
    print("GLM模型搜索能力对比测试")
    print("=" * 80)
    print()
    
    # 测试问题
    search_question = "请搜索今天北京的天气情况"
    general_question = "你好，请介绍一下自己"
    
    models_to_test = [
        "GLM-4.5",
        "GLM-4.5-Search", 
        "GLM-4.5-Thinking",
        "GLM-4.5-Air"
    ]
    
    print("🔍 测试搜索相关问题:")
    print(f"问题: {search_question}")
    print("-" * 80)
    
    for model in models_to_test:
        await test_model(model, search_question)
        print("-" * 40)
    
    print()
    print("💬 测试一般问题:")
    print(f"问题: {general_question}")
    print("-" * 80)
    
    for model in models_to_test:
        await test_model(model, general_question)
        print("-" * 40)
    
    print()
    print("=" * 80)
    print("测试完成")
    print("=" * 80)
    print()
    print("📋 分析要点:")
    print("1. GLM-4.5-Search 是否表现出不同的搜索行为？")
    print("2. 其他模型是否都拒绝搜索请求？")
    print("3. 模型响应中是否包含实际的搜索结果？")
    print("4. 检查服务器日志中的MCP服务器配置是否正确")

if __name__ == "__main__":
    asyncio.run(main())
