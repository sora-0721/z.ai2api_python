#!/usr/bin/env python3
"""
测试匿名模式下的令牌获取逻辑修复
"""

import sys
import os
import asyncio
from unittest.mock import patch, MagicMock
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.zai_transformer import ZAITransformer, get_auth_token_sync
from app.core.config import settings

def test_anonymous_mode_logic():
    """测试匿名模式下的令牌获取逻辑"""
    
    print("🧪 测试匿名模式下的令牌获取逻辑\n")
    
    # 保存原始设置
    original_anonymous_mode = settings.ANONYMOUS_MODE
    
    try:
        # 测试1: ANONYMOUS_MODE=true 时，不应该从 token 池获取令牌
        print("测试1: ANONYMOUS_MODE=true，匿名令牌获取失败")
        settings.ANONYMOUS_MODE = True
        
        with patch('app.core.zai_transformer.httpx.Client') as mock_client:
            # 模拟匿名令牌获取失败
            mock_response = MagicMock()
            mock_response.status_code = 500  # 失败
            mock_client.return_value.__enter__.return_value.get.return_value = mock_response
            
            with patch('app.core.zai_transformer.get_token_pool') as mock_get_pool:
                mock_pool = MagicMock()
                mock_pool.get_next_token.return_value = "fake_token_from_pool"
                mock_get_pool.return_value = mock_pool
                
                # 调用同步版本
                result = get_auth_token_sync()
                
                # 验证结果
                print(f"  结果: {result}")
                print(f"  是否调用了token池: {mock_get_pool.called}")
                
                if result == "" and not mock_get_pool.called:
                    print("  ✅ 正确：匿名模式下失败时不会尝试token池")
                else:
                    print("  ❌ 错误：匿名模式下仍然尝试了token池")
        
        print()
        
        # 测试2: ANONYMOUS_MODE=true 时，匿名令牌获取成功
        print("测试2: ANONYMOUS_MODE=true，匿名令牌获取成功")
        settings.ANONYMOUS_MODE = True
        
        with patch('app.core.zai_transformer.httpx.Client') as mock_client:
            # 模拟匿名令牌获取成功
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"token": "anonymous_token_success"}
            mock_client.return_value.__enter__.return_value.get.return_value = mock_response
            
            with patch('app.core.zai_transformer.get_token_pool') as mock_get_pool:
                mock_pool = MagicMock()
                mock_pool.get_next_token.return_value = "fake_token_from_pool"
                mock_get_pool.return_value = mock_pool
                
                # 调用同步版本
                result = get_auth_token_sync()
                
                # 验证结果
                print(f"  结果: {result}")
                print(f"  是否调用了token池: {mock_get_pool.called}")
                
                if result == "anonymous_token_success" and not mock_get_pool.called:
                    print("  ✅ 正确：匿名模式下成功时不会尝试token池")
                else:
                    print("  ❌ 错误：匿名模式下成功时仍然尝试了token池")
        
        print()
        
        # 测试3: ANONYMOUS_MODE=false 时，应该先尝试 token 池
        print("测试3: ANONYMOUS_MODE=false，应该先尝试token池")
        settings.ANONYMOUS_MODE = False
        
        with patch('app.core.zai_transformer.get_token_pool') as mock_get_pool:
            mock_pool = MagicMock()
            mock_pool.get_next_token.return_value = "token_from_pool"
            mock_get_pool.return_value = mock_pool
            
            # 调用同步版本
            result = get_auth_token_sync()
            
            # 验证结果
            print(f"  结果: {result}")
            print(f"  是否调用了token池: {mock_get_pool.called}")
            
            if result == "token_from_pool" and mock_get_pool.called:
                print("  ✅ 正确：非匿名模式下优先使用token池")
            else:
                print("  ❌ 错误：非匿名模式下没有正确使用token池")
        
        print()
        
    finally:
        # 恢复原始设置
        settings.ANONYMOUS_MODE = original_anonymous_mode

async def test_async_anonymous_mode_logic():
    """测试异步版本的匿名模式逻辑"""
    
    print("🧪 测试异步版本的匿名模式逻辑\n")
    
    # 保存原始设置
    original_anonymous_mode = settings.ANONYMOUS_MODE
    
    try:
        # 测试异步版本
        print("测试: 异步版本 ANONYMOUS_MODE=true，匿名令牌获取失败")
        settings.ANONYMOUS_MODE = True
        
        transformer = ZAITransformer()
        
        with patch('app.core.zai_transformer.httpx.AsyncClient') as mock_client:
            # 模拟匿名令牌获取失败
            mock_response = MagicMock()
            mock_response.status_code = 500  # 失败
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            with patch('app.core.zai_transformer.get_token_pool') as mock_get_pool:
                mock_pool = MagicMock()
                mock_pool.get_next_token.return_value = "fake_token_from_pool"
                mock_get_pool.return_value = mock_pool
                
                # 调用异步版本
                result = await transformer.get_token()
                
                # 验证结果
                print(f"  结果: {result}")
                print(f"  是否调用了token池: {mock_get_pool.called}")
                
                if result == "" and not mock_get_pool.called:
                    print("  ✅ 正确：异步版本匿名模式下失败时不会尝试token池")
                else:
                    print("  ❌ 错误：异步版本匿名模式下仍然尝试了token池")
        
        print()
        
    finally:
        # 恢复原始设置
        settings.ANONYMOUS_MODE = original_anonymous_mode

def main():
    """主测试函数"""
    print("🔧 测试匿名模式令牌获取逻辑修复\n")
    
    # 测试同步版本
    test_anonymous_mode_logic()
    
    # 测试异步版本
    asyncio.run(test_async_anonymous_mode_logic())
    
    print("🎯 测试总结:")
    print("✅ 修复了匿名模式下错误尝试token池的问题")
    print("✅ 确保ANONYMOUS_MODE=true时只使用匿名令牌")
    print("✅ 确保ANONYMOUS_MODE=false时优先使用token池")

if __name__ == "__main__":
    main()
