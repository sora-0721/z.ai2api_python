#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试GLM-4.5-Search模型的deep-web-search MCP服务器功能
"""

import asyncio
import json
import httpx
from app.core.config import settings
from app.core.zai_transformer import ZAITransformer
from app.utils.logger import setup_logger

# 设置日志
logger = setup_logger(log_dir="logs", debug_mode=True)

async def test_search_model_mcp():
    """测试搜索模型的MCP服务器配置"""
    
    # 创建转换器实例
    transformer = ZAITransformer()
    
    # 模拟OpenAI请求 - 使用GLM-4.5-Search模型
    openai_request = {
        "model": "GLM-4.5-Search",
        "messages": [
            {"role": "user", "content": "请搜索一下今天的新闻"}
        ],
        "stream": True
    }
    
    print(f"🧪 测试请求:")
    print(f"  模型: {openai_request['model']}")
    print(f"  SEARCH_MODEL配置: {settings.SEARCH_MODEL}")
    print(f"  模型匹配: {openai_request['model'] == settings.SEARCH_MODEL}")
    print()
    
    try:
        # 转换请求
        transformed = await transformer.transform_request_in(openai_request)
        
        print(f"✅ 转换成功!")
        print(f"  上游模型: {transformed['body']['model']}")
        print(f"  MCP服务器: {transformed['body']['mcp_servers']}")
        print(f"  web_search特性: {transformed['body']['features']['web_search']}")
        print(f"  auto_web_search特性: {transformed['body']['features']['auto_web_search']}")
        print()
        
        # 检查是否正确添加了deep-web-search
        mcp_servers = transformed['body']['mcp_servers']
        if "deep-web-search" in mcp_servers:
            print("✅ deep-web-search MCP服务器已正确添加!")
        else:
            print("❌ deep-web-search MCP服务器未添加!")
            print(f"   实际MCP服务器列表: {mcp_servers}")
        
        return transformed
        
    except Exception as e:
        print(f"❌ 转换失败: {e}")
        return None

async def test_non_search_model():
    """测试非搜索模型不应该添加MCP服务器"""
    
    transformer = ZAITransformer()
    
    # 模拟OpenAI请求 - 使用普通GLM-4.5模型
    openai_request = {
        "model": "GLM-4.5",
        "messages": [
            {"role": "user", "content": "你好"}
        ],
        "stream": True
    }
    
    print(f"🧪 测试普通模型:")
    print(f"  模型: {openai_request['model']}")
    print()
    
    try:
        # 转换请求
        transformed = await transformer.transform_request_in(openai_request)
        
        print(f"✅ 转换成功!")
        print(f"  上游模型: {transformed['body']['model']}")
        print(f"  MCP服务器: {transformed['body']['mcp_servers']}")
        print(f"  web_search特性: {transformed['body']['features']['web_search']}")
        print()
        
        # 检查MCP服务器列表应该为空
        mcp_servers = transformed['body']['mcp_servers']
        if not mcp_servers:
            print("✅ 普通模型正确地没有添加MCP服务器!")
        else:
            print(f"❌ 普通模型意外添加了MCP服务器: {mcp_servers}")
        
        return transformed
        
    except Exception as e:
        print(f"❌ 转换失败: {e}")
        return None

async def test_actual_request():
    """测试实际的HTTP请求"""
    
    print(f"🌐 测试实际HTTP请求到本地服务器...")
    
    # 检查服务器是否运行
    try:
        async with httpx.AsyncClient() as client:
            # 测试服务器是否可达
            response = await client.get(f"http://localhost:{settings.LISTEN_PORT}/v1/models", timeout=5.0)
            if response.status_code != 200:
                print(f"❌ 服务器未运行或不可达: {response.status_code}")
                return
                
            print(f"✅ 服务器运行正常")
            
            # 发送搜索模型请求
            search_request = {
                "model": "GLM-4.5-Search",
                "messages": [
                    {"role": "user", "content": "搜索今天的天气"}
                ],
                "stream": False
            }
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.AUTH_TOKEN}"
            }
            
            print(f"📤 发送搜索请求...")
            response = await client.post(
                f"http://localhost:{settings.LISTEN_PORT}/v1/chat/completions",
                json=search_request,
                headers=headers,
                timeout=30.0
            )
            
            print(f"📥 响应状态: {response.status_code}")
            if response.status_code == 200:
                print(f"✅ 请求成功!")
                # 不打印完整响应，只显示状态
            else:
                print(f"❌ 请求失败: {response.text}")
                
    except httpx.ConnectError:
        print(f"❌ 无法连接到服务器 localhost:{settings.LISTEN_PORT}")
        print(f"   请确保服务器正在运行: python main.py")
    except Exception as e:
        print(f"❌ 请求异常: {e}")

async def main():
    """主测试函数"""
    print("=" * 60)
    print("GLM-4.5-Search MCP服务器测试")
    print("=" * 60)
    print()
    
    # 测试1: 搜索模型应该添加MCP服务器
    await test_search_model_mcp()
    print()
    
    # 测试2: 普通模型不应该添加MCP服务器
    await test_non_search_model()
    print()
    
    # 测试3: 实际HTTP请求（如果服务器运行）
    await test_actual_request()
    print()
    
    print("=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
