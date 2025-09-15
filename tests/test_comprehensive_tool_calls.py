#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
全面的工具调用测试套件
覆盖各种工具类型、参数格式、传输模式和边界情况
"""

import json
import time
from typing import Dict, Any, List
from app.utils.sse_tool_handler import SSEToolHandler
from app.utils.logger import get_logger

logger = get_logger()

class TestResult:
    """测试结果统计"""
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def add_pass(self):
        self.passed += 1
    
    def add_fail(self, error_msg: str):
        self.failed += 1
        self.errors.append(error_msg)
    
    def print_summary(self):
        total = self.passed + self.failed
        success_rate = (self.passed / total * 100) if total > 0 else 0
        
        print(f"\n📊 {self.test_name} 测试汇总:")
        print(f"  总测试数: {total}")
        print(f"  ✅ 通过: {self.passed}")
        print(f"  ❌ 失败: {self.failed}")
        print(f"  📈 成功率: {success_rate:.1f}%")
        
        if self.errors:
            print(f"\n❌ 失败详情:")
            for i, error in enumerate(self.errors, 1):
                print(f"  {i}. {error}")

def test_various_tool_types():
    """测试各种类型的工具调用"""
    
    result = TestResult("工具类型测试")
    
    # 定义各种工具类型的测试用例
    tool_scenarios = [
        {
            "name": "浏览器导航工具",
            "tool_name": "browser_navigate",
            "arguments": '{"url": "https://www.google.com"}',
            "expected_args": {"url": "https://www.google.com"},
            "description": "测试浏览器导航工具的URL参数"
        },
        {
            "name": "天气查询工具",
            "tool_name": "get_weather",
            "arguments": '{"city": "北京", "unit": "celsius"}',
            "expected_args": {"city": "北京", "unit": "celsius"},
            "description": "测试天气查询工具的城市和单位参数"
        },
        {
            "name": "文件操作工具",
            "tool_name": "file_write",
            "arguments": '{"path": "/tmp/test.txt", "content": "Hello World", "encoding": "utf-8"}',
            "expected_args": {"path": "/tmp/test.txt", "content": "Hello World", "encoding": "utf-8"},
            "description": "测试文件写入工具的多参数"
        },
        {
            "name": "搜索工具",
            "tool_name": "web_search",
            "arguments": '{"query": "Python编程", "limit": 10, "safe_search": true}',
            "expected_args": {"query": "Python编程", "limit": 10, "safe_search": True},
            "description": "测试搜索工具的混合类型参数"
        },
        {
            "name": "数据库查询工具",
            "tool_name": "db_query",
            "arguments": '{"sql": "SELECT * FROM users WHERE age > ?", "params": [18], "timeout": 30.5}',
            "expected_args": {"sql": "SELECT * FROM users WHERE age > ?", "params": [18], "timeout": 30.5},
            "description": "测试数据库工具的复杂参数结构"
        },
        {
            "name": "API调用工具",
            "tool_name": "api_call",
            "arguments": '{"method": "POST", "url": "https://api.example.com/data", "headers": {"Content-Type": "application/json"}, "body": {"key": "value"}}',
            "expected_args": {"method": "POST", "url": "https://api.example.com/data", "headers": {"Content-Type": "application/json"}, "body": {"key": "value"}},
            "description": "测试API调用工具的嵌套对象参数"
        },
        {
            "name": "图像处理工具",
            "tool_name": "image_resize",
            "arguments": '{"input_path": "image.jpg", "output_path": "resized.jpg", "width": 800, "height": 600, "maintain_aspect": false}',
            "expected_args": {"input_path": "image.jpg", "output_path": "resized.jpg", "width": 800, "height": 600, "maintain_aspect": False},
            "description": "测试图像处理工具的数值和布尔参数"
        },
        {
            "name": "邮件发送工具",
            "tool_name": "send_email",
            "arguments": '{"to": ["user1@example.com", "user2@example.com"], "subject": "测试邮件", "body": "这是一封测试邮件\\n包含换行符", "attachments": []}',
            "expected_args": {"to": ["user1@example.com", "user2@example.com"], "subject": "测试邮件", "body": "这是一封测试邮件\n包含换行符", "attachments": []},
            "description": "测试邮件工具的数组参数和转义字符"
        }
    ]
    
    print("🔧 测试各种类型的工具调用")
    print("=" * 80)
    
    for i, scenario in enumerate(tool_scenarios, 1):
        print(f"\n测试 {i}: {scenario['name']}")
        print(f"描述: {scenario['description']}")
        
        try:
            handler = SSEToolHandler("test_chat_id", "GLM-4.5")
            
            # 构造完整的工具调用数据
            tool_data = {
                "edit_index": 0,
                "edit_content": f'<glm_block >{{"type": "mcp", "data": {{"metadata": {{"id": "call_{i}", "name": "{scenario["tool_name"]}", "arguments": "{scenario["arguments"]}", "result": "", "status": "completed"}}}}, "thought": null}}</glm_block>',
                "phase": "tool_call"
            }
            
            # 处理工具调用
            chunks = list(handler.process_tool_call_phase(tool_data, is_stream=False))
            
            # 验证结果
            if handler.active_tools:
                tool = list(handler.active_tools.values())[0]
                actual_args = tool["arguments"]
                expected_args = scenario["expected_args"]
                
                if actual_args == expected_args:
                    print(f"  ✅ 参数解析正确: {actual_args}")
                    result.add_pass()
                else:
                    error_msg = f"{scenario['name']}: 参数不匹配 - 期望: {expected_args}, 实际: {actual_args}"
                    print(f"  ❌ {error_msg}")
                    result.add_fail(error_msg)
            else:
                error_msg = f"{scenario['name']}: 未检测到工具调用"
                print(f"  ❌ {error_msg}")
                result.add_fail(error_msg)
                
        except Exception as e:
            error_msg = f"{scenario['name']}: 处理异常 - {str(e)}"
            print(f"  ❌ {error_msg}")
            result.add_fail(error_msg)
    
    result.print_summary()
    return result

def test_parameter_formats():
    """测试各种参数格式"""
    
    result = TestResult("参数格式测试")
    
    # 定义各种参数格式的测试用例
    format_scenarios = [
        {
            "name": "空参数",
            "arguments": "{}",
            "expected": {},
            "description": "测试空参数对象"
        },
        {
            "name": "null参数",
            "arguments": "null",
            "expected": {},
            "description": "测试null参数值"
        },
        {
            "name": "转义JSON字符串",
            "arguments": '{\\"key\\": \\"value\\"}',
            "expected": {"key": "value"},
            "description": "测试转义的JSON字符串"
        },
        {
            "name": "包含特殊字符",
            "arguments": '{"text": "Hello\\nWorld\\t!", "emoji": "😀🎉", "unicode": "中文测试"}',
            "expected": {"text": "Hello\nWorld\t!", "emoji": "😀🎉", "unicode": "中文测试"},
            "description": "测试包含换行符、制表符、emoji和中文的参数"
        },
        {
            "name": "数值类型",
            "arguments": '{"int": 42, "float": 3.14159, "negative": -100, "zero": 0}',
            "expected": {"int": 42, "float": 3.14159, "negative": -100, "zero": 0},
            "description": "测试各种数值类型参数"
        },
        {
            "name": "布尔类型",
            "arguments": '{"true_val": true, "false_val": false}',
            "expected": {"true_val": True, "false_val": False},
            "description": "测试布尔类型参数"
        },
        {
            "name": "数组参数",
            "arguments": '{"empty_array": [], "string_array": ["a", "b", "c"], "mixed_array": [1, "two", true, null]}',
            "expected": {"empty_array": [], "string_array": ["a", "b", "c"], "mixed_array": [1, "two", True, None]},
            "description": "测试各种数组类型参数"
        },
        {
            "name": "嵌套对象",
            "arguments": '{"nested": {"level1": {"level2": {"value": "deep"}}}, "array_of_objects": [{"id": 1}, {"id": 2}]}',
            "expected": {"nested": {"level1": {"level2": {"value": "deep"}}}, "array_of_objects": [{"id": 1}, {"id": 2}]},
            "description": "测试深度嵌套的对象和对象数组"
        },
        {
            "name": "长字符串",
            "arguments": '{"long_text": "' + "A" * 1000 + '"}',
            "expected": {"long_text": "A" * 1000},
            "description": "测试长字符串参数"
        },
        {
            "name": "包含引号的字符串",
            "arguments": '{"quoted": "He said \\"Hello\\" to me", "single_quote": "It\'s working"}',
            "expected": {"quoted": 'He said "Hello" to me', "single_quote": "It's working"},
            "description": "测试包含引号的字符串参数"
        }
    ]
    
    print("\n📝 测试各种参数格式")
    print("=" * 80)
    
    for i, scenario in enumerate(format_scenarios, 1):
        print(f"\n测试 {i}: {scenario['name']}")
        print(f"描述: {scenario['description']}")
        
        try:
            handler = SSEToolHandler("test_chat_id", "GLM-4.5")
            
            # 直接测试参数解析
            result_args = handler._parse_partial_arguments(scenario["arguments"])
            
            if result_args == scenario["expected"]:
                print(f"  ✅ 参数解析正确")
                result.add_pass()
            else:
                error_msg = f"{scenario['name']}: 参数解析错误 - 期望: {scenario['expected']}, 实际: {result_args}"
                print(f"  ❌ {error_msg}")
                result.add_fail(error_msg)
                
        except Exception as e:
            error_msg = f"{scenario['name']}: 解析异常 - {str(e)}"
            print(f"  ❌ {error_msg}")
            result.add_fail(error_msg)
    
    result.print_summary()
    return result
