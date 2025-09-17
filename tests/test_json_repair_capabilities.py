#!/usr/bin/env python3
"""
测试 json-repair 库的能力，评估哪些预处理步骤可以交给它处理
"""

import sys
import os
import json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from json_repair import repair_json

def test_json_repair_capabilities():
    """测试 json-repair 库对各种 JSON 问题的处理能力"""
    
    print("🧪 测试 json-repair 库的能力\n")
    
    # 测试用例：从当前代码中提取的各种问题场景
    test_cases = [
        {
            "name": "缺少开始括号",
            "input": '"command":"echo hello","description":"test"}',
            "expected_fixable": True
        },
        {
            "name": "简单转义引号",
            "input": '{"command":"echo \\"hello\\"","description":"test"}',
            "expected_fixable": True
        },
        {
            "name": "Windows路径过度转义",
            "input": '{"path":"C:\\\\\\\\Users\\\\\\\\Documents"}',
            "expected_fixable": True
        },
        {
            "name": "复杂命令行参数",
            "input": '{"command":"echo \\"添加更多内容\\uff1a$(date)\\\\\\" >> \\\\\\"C:\\\\\\\\Users\\\\\\\\test\\\\\\\\1.txt\\\\\\"\\"","description":"test"}',
            "expected_fixable": True
        },
        {
            "name": "包含result字段的额外内容",
            "input": '{"command":"echo hello","description":"test"}, "result": null',
            "expected_fixable": False  # 这个可能需要预处理
        },
        {
            "name": "简单字段转义引号模式",
            "input": '{"name:\\"value\\","description":"test"}',
            "expected_fixable": True
        },
        {
            "name": "命令末尾多余引号",
            "input": '{"command":"echo hello > file.txt\\"","description":"test"}',
            "expected_fixable": True
        },
        {
            "name": "路径末尾引号模式",
            "input": '{"command":"dir \\"C:\\\\Users\\\\\\"","description":"test"}',
            "expected_fixable": True
        },
        {
            "name": "正常JSON（无问题）",
            "input": '{"command":"echo hello","description":"test"}',
            "expected_fixable": True
        },
        {
            "name": "空对象",
            "input": '{}',
            "expected_fixable": True
        }
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"测试 {i}: {test_case['name']}")
        print(f"  输入: {test_case['input'][:100]}{'...' if len(test_case['input']) > 100 else ''}")
        
        try:
            # 测试 json-repair 的直接修复能力
            repaired = repair_json(test_case['input'])
            print(f"  修复结果: {repaired[:100]}{'...' if len(repaired) > 100 else ''}")
            
            # 验证修复结果是否为有效JSON
            parsed = json.loads(repaired)
            print(f"  ✅ 修复成功，解析为: {type(parsed)}")
            
            # 检查修复质量
            if isinstance(parsed, dict):
                if 'command' in parsed:
                    command = parsed['command']
                    # 检查是否还有明显的问题
                    has_issues = (
                        command.endswith('""') or  # 多余引号
                        '\\\\\\\\' in command or   # 过度转义
                        command.count('"') % 2 != 0  # 引号不匹配
                    )
                    if has_issues:
                        print(f"  ⚠️ 修复后仍有问题: {command}")
                    else:
                        print(f"  ✅ 修复质量良好")
                        
            results.append({
                'name': test_case['name'],
                'success': True,
                'repaired': repaired,
                'parsed': parsed
            })
            
        except Exception as e:
            print(f"  ❌ 修复失败: {e}")
            results.append({
                'name': test_case['name'],
                'success': False,
                'error': str(e)
            })
        
        print()
    
    # 统计结果
    successful = sum(1 for r in results if r['success'])
    total = len(results)
    
    print(f"📊 测试结果统计:")
    print(f"  成功修复: {successful}/{total} ({successful/total*100:.1f}%)")
    print(f"  失败案例: {total-successful}")
    
    # 分析哪些问题 json-repair 无法处理
    failed_cases = [r for r in results if not r['success']]
    if failed_cases:
        print(f"\n❌ json-repair 无法处理的问题:")
        for case in failed_cases:
            print(f"  - {case['name']}: {case['error']}")
    
    # 分析哪些问题修复后仍有质量问题
    quality_issues = []
    for r in results:
        if r['success'] and isinstance(r.get('parsed'), dict):
            if 'command' in r['parsed']:
                command = r['parsed']['command']
                if (command.endswith('""') or '\\\\\\\\' in command or 
                    command.count('"') % 2 != 0):
                    quality_issues.append(r['name'])
    
    if quality_issues:
        print(f"\n⚠️ 修复后仍有质量问题的案例:")
        for case_name in quality_issues:
            print(f"  - {case_name}")
    
    return results

def test_specific_preprocessing_needs():
    """测试特定的预处理需求"""

    print("\n🔍 测试特定预处理需求\n")

    # 测试包含额外内容的情况
    test_with_extra = '{"command":"echo hello","description":"test"}, "result": null, "status": "complete"'

    print("测试包含额外内容的JSON:")
    print(f"  原始: {test_with_extra}")

    try:
        # 直接用 json-repair 修复
        repaired = repair_json(test_with_extra)
        print(f"  json-repair 结果: {repaired}")

        # 检查是否正确提取了主要部分
        parsed = json.loads(repaired)
        if isinstance(parsed, dict) and 'command' in parsed and 'description' in parsed:
            print("  ✅ json-repair 能够处理额外内容")
        else:
            print("  ❌ json-repair 无法正确处理额外内容，需要预处理")

    except Exception as e:
        print(f"  ❌ json-repair 处理失败: {e}")
        print("  需要预处理来提取纯JSON部分")

def test_edge_cases():
    """测试边缘情况"""

    print("\n🔍 测试边缘情况\n")

    edge_cases = [
        {
            "name": "缺少开始括号但有复杂内容",
            "input": '"command":"echo \\"hello\\"","description":"test"}',
        },
        {
            "name": "多层嵌套转义",
            "input": '{"command":"echo \\\\\\"hello\\\\\\"","description":"test"}',
        },
        {
            "name": "混合引号问题",
            "input": '{"command":"echo \\"hello\\" > \\"file.txt\\"","description":"test"}',
        },
        {
            "name": "路径中的特殊字符",
            "input": '{"path":"C:\\\\Users\\\\test\\\\file with spaces.txt"}',
        }
    ]

    for i, case in enumerate(edge_cases, 1):
        print(f"边缘测试 {i}: {case['name']}")
        print(f"  输入: {case['input']}")

        try:
            repaired = repair_json(case['input'])
            parsed = json.loads(repaired)
            print(f"  ✅ 成功: {repaired}")
        except Exception as e:
            print(f"  ❌ 失败: {e}")
        print()

if __name__ == "__main__":
    test_json_repair_capabilities()
    test_specific_preprocessing_needs()
    test_edge_cases()
