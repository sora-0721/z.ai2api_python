#!/usr/bin/env python3
"""
测试命令引号修复功能
"""

import sys
import os
import json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.sse_tool_handler import SSEToolHandler

def test_command_quote_fix():
    """测试命令引号修复功能"""
    
    handler = SSEToolHandler("test-model", stream=False)
    
    test_cases = [
        {
            "name": "日志中的实际问题",
            "input": '{"command":"echo \\"添加更多内容\\uff1a$(date)\\\\\\" >> \\\\\\"C:\\\\\\\\Users\\\\\\\\cassianvale\\\\\\\\Documents\\\\\\\\GitHub\\\\\\\\z.ai2api_python\\\\\\\\1.txt\\\\\\"\\"","description":"\\u54111.txt\\u6587\\u4ef6\\u6dfb\\u52a0\\u5f53\\u524d\\u65f6\\u95f4\\u6233\\u5185\\u5bb9"}',
            "expected_no_double_quotes": True
        },
        {
            "name": "简单的双引号问题",
            "input": '{"command":"echo \\"hello\\" > \\"file.txt\\"","description":"test"}',
            "expected_no_double_quotes": True
        },
        {
            "name": "正常命令（无问题）",
            "input": '{"command":"echo hello > file.txt","description":"test"}',
            "expected_no_double_quotes": True
        },
        {
            "name": "复杂路径命令",
            "input": '{"command":"dir \\"C:\\\\Users\\\\test\\"","description":"list directory"}',
            "expected_no_double_quotes": True
        }
    ]
    
    print("🧪 测试命令引号修复功能")
    print()
    
    passed = 0
    total = len(test_cases)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"测试 {i}: {test_case['name']}")
        print(f"  输入: {test_case['input'][:100]}{'...' if len(test_case['input']) > 100 else ''}")
        
        try:
            result_str = handler._fix_tool_arguments(test_case['input'])
            result = json.loads(result_str)
            
            if 'command' in result:
                command = result['command']
                print(f"  命令: {command}")
                
                # 检查是否有多余的引号
                has_double_quotes = command.endswith('""')
                
                if test_case['expected_no_double_quotes'] and not has_double_quotes:
                    print("  ✅ 引号修复正确")
                    passed += 1
                elif not test_case['expected_no_double_quotes'] and has_double_quotes:
                    print("  ✅ 保持预期的引号")
                    passed += 1
                else:
                    print(f"  ❌ 引号处理错误，期望无双引号: {test_case['expected_no_double_quotes']}, 实际有双引号: {has_double_quotes}")
            else:
                print("  ❌ 结果中没有command字段")
                
        except Exception as e:
            print(f"  ❌ 处理失败: {e}")
        
        print()
    
    print(f"📊 测试结果: {passed}/{total} 个测试通过")
    
    if passed == total:
        print("🎉 所有命令引号修复测试通过！")
    else:
        print("⚠️ 部分测试失败，需要进一步修复")

if __name__ == "__main__":
    test_command_quote_fix()
