#!/usr/bin/env python3
"""
测试 json-repair 库的修复功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.sse_tool_handler import SSEToolHandler

def test_json_repair():
    """测试 json-repair 修复功能"""
    
    handler = SSEToolHandler("test-model", stream=False)
    
    # 测试用例：您提到的具体问题数据
    test_cases = [
        {
            "name": "实际日志中的问题数据",
            "input": '{"type":"png","filename:\\"bilibili_homepage\\",\\"element":"viewport","ref":"viewport","fullPage":false',
            "expected_keys": ["type", "filename", "element", "ref", "fullPage"]
        },
        {
            "name": "转义引号结尾问题1",
            "input": '{"url":"https://bilibili.com\\"',
            "expected_keys": ["url"]
        },
        {
            "name": "转义引号结尾问题2", 
            "input": '{"url":"https://bilibili.com\\"}',
            "expected_keys": ["url"]
        },
        {
            "name": "转义引号结尾问题3",
            "input": '{"url":"https://bilibili.com\\"}\"',
            "expected_keys": ["url"]
        },
        {
            "name": "复杂转义引号",
            "input": '{"type":"png","filename:\\"test_file\\",\\"element":"body","width":1920',
            "expected_keys": ["type", "filename", "element", "width"]
        },
        {
            "name": "缺少开始括号",
            "input": '"url":"https://example.com"}',
            "expected_keys": ["url"]
        },
        {
            "name": "正常JSON（无需修复）",
            "input": '{"url":"https://example.com","type":"test"}',
            "expected_keys": ["url", "type"]
        }
    ]
    
    print("🧪 测试 json-repair 修复功能\n")
    
    success_count = 0
    total_count = len(test_cases)
    
    for i, case in enumerate(test_cases, 1):
        print(f"测试 {i}: {case['name']}")
        print(f"  输入: {case['input']}")
        
        try:
            # 调用修复函数
            fixed = handler._fix_tool_arguments(case['input'])
            print(f"  输出: {fixed}")
            
            # 验证结果是否为有效JSON
            import json
            try:
                parsed = json.loads(fixed)
                print(f"  ✅ JSON 解析成功")
                
                # 检查是否包含期望的键
                missing_keys = []
                for key in case['expected_keys']:
                    if key not in parsed:
                        missing_keys.append(key)
                
                if missing_keys:
                    print(f"  ⚠️ 缺少键: {missing_keys}")
                else:
                    print(f"  ✅ 包含所有期望的键: {case['expected_keys']}")
                    success_count += 1
                    
            except json.JSONDecodeError as e:
                print(f"  ❌ JSON 解析失败: {e}")
                
        except Exception as e:
            print(f"  ❌ 修复异常: {e}")
            
        print()
    
    print(f"📊 测试结果: {success_count}/{total_count} 个测试通过")
    
    # 测试 json-repair 库是否可用
    print("\n🔍 检查 json-repair 库:")
    try:
        from json_repair import repair_json
        test_json = '{"key": "value"'
        repaired = repair_json(test_json)
        print(f"  ✅ json-repair 库可用")
        print(f"  测试修复: {test_json} → {repaired}")
    except ImportError:
        print(f"  ❌ json-repair 库未安装")
    except Exception as e:
        print(f"  ❌ json-repair 库错误: {e}")

if __name__ == "__main__":
    test_json_repair()
