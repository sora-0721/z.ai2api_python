#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试优化后的SSE工具调用处理器
基于真实的Z.AI响应格式和日志数据进行全面测试
"""

import json
import time
import traceback
from typing import List, Dict, Any
from app.utils.sse_tool_handler import SSEToolHandler
from app.utils.logger import get_logger

logger = get_logger()


class TestResult:
    """测试结果类"""
    def __init__(self, name: str):
        self.name = name
        self.passed = 0
        self.failed = 0
        self.errors = []

    def add_pass(self):
        self.passed += 1

    def add_fail(self, error: str):
        self.failed += 1
        self.errors.append(error)

    def print_summary(self):
        total = self.passed + self.failed
        success_rate = (self.passed / total * 100) if total > 0 else 0

        print(f"\n📊 {self.name} 测试结果:")
        print(f"  ✅ 通过: {self.passed}")
        print(f"  ❌ 失败: {self.failed}")
        print(f"  📈 成功率: {success_rate:.1f}%")

        if self.errors:
            print(f"  🔍 错误详情:")
            for i, error in enumerate(self.errors, 1):
                print(f"    {i}. {error}")


def parse_openai_chunk(chunk_data: str) -> Dict[str, Any]:
    """解析OpenAI格式的chunk数据"""
    try:
        if chunk_data.startswith("data: "):
            chunk_data = chunk_data[6:]  # 移除 "data: " 前缀
        if chunk_data.strip() == "[DONE]":
            return {"type": "done"}
        return json.loads(chunk_data)
    except json.JSONDecodeError:
        return {"type": "invalid", "raw": chunk_data}


def extract_tool_calls(chunks: List[str]) -> List[Dict[str, Any]]:
    """从chunk列表中提取工具调用信息"""
    tools = []
    current_tool = None

    for chunk in chunks:
        parsed = parse_openai_chunk(chunk)
        if parsed.get("type") == "invalid":
            continue

        choices = parsed.get("choices", [])
        if not choices:
            continue

        delta = choices[0].get("delta", {})
        tool_calls = delta.get("tool_calls", [])

        for tc in tool_calls:
            if tc.get("function", {}).get("name"):  # 新工具开始
                current_tool = {
                    "id": tc.get("id"),
                    "name": tc["function"]["name"],
                    "arguments": ""
                }
                tools.append(current_tool)
            elif tc.get("function", {}).get("arguments") and current_tool:  # 参数累积
                current_tool["arguments"] += tc["function"]["arguments"]

    # 解析最终参数
    for tool in tools:
        try:
            tool["parsed_arguments"] = json.loads(tool["arguments"]) if tool["arguments"] else {}
        except json.JSONDecodeError:
            tool["parsed_arguments"] = {}

    return tools


def test_real_world_scenarios():
    """测试基于真实Z.AI响应的工具调用处理"""

    result = TestResult("真实场景测试")

    # 基于实际日志的测试数据
    test_scenarios = [
        {
            "name": "浏览器导航工具调用",
            "description": "模拟打开Google网站的工具调用",
            "expected_tools": [
                {
                    "name": "playwri-browser_navigate",
                    "id": "call_fyh97tn03ow",
                    "arguments": {"url": "https://www.google.com"}
                }
            ],
            "data_sequence": [
                {
                    "edit_index": 22,
                    "edit_content": '\n\n<glm_block >{"type": "mcp", "data": {"metadata": {"id": "call_fyh97tn03ow", "name": "playwri-browser_navigate", "arguments": "{\\"url\\":\\"https://www.goo',
                    "phase": "tool_call"
                },
                {
                    "edit_index": 176,
                    "edit_content": 'gle.com\\"}", "result": "", "display_result": "", "duration": "...", "status": "completed", "is_error": false, "mcp_server": {"name": "mcp-server"}}, "thought": null, "ppt": null, "browser": null}}</glm_block>',
                    "phase": "tool_call"
                },
                {
                    "edit_index": 199,
                    "edit_content": 'null, "display_result": "", "duration": "...", "status": "completed", "is_error": false, "mcp_server": {"name": "mcp-server"}}, "thought": null, "ppt": null, "browser": null}}</glm_block>',
                    "phase": "other"
                }
            ]
        },
        {
            "name": "天气查询工具调用",
            "description": "模拟查询上海天气的工具调用",
            "expected_tools": [
                {
                    "name": "search",
                    "id": "call_qsn2jby8al",
                    "arguments": {"queries": ["今天上海天气", "上海天气预报 今天"]}
                }
            ],
            "data_sequence": [
                {
                    "edit_index": 16,
                    "edit_content": '\n\n<glm_block >{"type": "mcp", "data": {"metadata": {"id": "call_qsn2jby8al", "name": "search", "arguments": "{\\"queries\\":[\\"今天上海天气\\", \\"',
                    "phase": "tool_call"
                },
                {
                    "edit_index": 183,
                    "edit_content": '上海天气预报 今天\\"]}", "result": "", "display_result": "", "duration": "...", "status": "completed", "is_error": false, "mcp_server": {"name": "mcp-server"}}, "thought": null, "ppt": null, "browser": null}}</glm_block>',
                    "phase": "tool_call"
                }
            ]
        },
        {
            "name": "多工具调用序列",
            "description": "模拟连续的多个工具调用",
            "expected_tools": [
                {
                    "name": "search",
                    "id": "call_001",
                    "arguments": {"query": "北京天气"}
                },
                {
                    "name": "visit_page",
                    "id": "call_002",
                    "arguments": {"url": "https://weather.com"}
                }
            ],
            "data_sequence": [
                {
                    "edit_index": 0,
                    "edit_content": '<glm_block >{"type": "mcp", "data": {"metadata": {"id": "call_001", "name": "search", "arguments": "{\\"query\\":\\"北京天气\\"}", "result": "", "status": "completed"}}, "thought": null}}</glm_block>',
                    "phase": "tool_call"
                },
                {
                    "edit_index": 200,
                    "edit_content": '\n\n<glm_block >{"type": "mcp", "data": {"metadata": {"id": "call_002", "name": "visit_page", "arguments": "{\\"url\\":\\"https://weather.com\\"}", "result": "", "status": "completed"}}, "thought": null}}</glm_block>',
                    "phase": "tool_call"
                }
            ]
        }
    ]

    print(f"\n🧪 开始执行 {len(test_scenarios)} 个真实场景测试...")

    # 执行每个测试场景
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n{'='*60}")
        print(f"测试 {i}: {scenario['name']}")
        print(f"描述: {scenario['description']}")
        print('='*60)

        try:
            # 创建新的处理器实例
            handler = SSEToolHandler("test_chat_id", "GLM-4.5")

            # 处理数据序列
            all_chunks = []
            for j, data in enumerate(scenario["data_sequence"]):
                print(f"\n📦 处理数据块 {j+1}: phase={data['phase']}, edit_index={data['edit_index']}")

                if data["phase"] == "tool_call":
                    chunks = list(handler.process_tool_call_phase(data, is_stream=True))
                else:
                    chunks = list(handler.process_other_phase(data, is_stream=True))

                all_chunks.extend(chunks)

            # 提取工具调用信息
            extracted_tools = extract_tool_calls(all_chunks)

            # 验证结果
            expected_tools = scenario["expected_tools"]

            print(f"\n📊 验证结果:")
            print(f"  期望工具数: {len(expected_tools)}")
            print(f"  实际工具数: {len(extracted_tools)}")

            # 详细验证每个工具
            for k, expected_tool in enumerate(expected_tools):
                if k < len(extracted_tools):
                    actual_tool = extracted_tools[k]

                    # 验证工具名称
                    name_match = actual_tool["name"] == expected_tool["name"]
                    # 验证工具ID
                    id_match = actual_tool["id"] == expected_tool["id"]
                    # 验证参数
                    args_match = actual_tool["parsed_arguments"] == expected_tool["arguments"]

                    if name_match and id_match and args_match:
                        print(f"  ✅ 工具 {k+1}: {expected_tool['name']} - 验证通过")
                        result.add_pass()
                    else:
                        error_details = []
                        if not name_match:
                            error_details.append(f"名称不匹配: 期望'{expected_tool['name']}', 实际'{actual_tool['name']}'")
                        if not id_match:
                            error_details.append(f"ID不匹配: 期望'{expected_tool['id']}', 实际'{actual_tool['id']}'")
                        if not args_match:
                            error_details.append(f"参数不匹配: 期望{expected_tool['arguments']}, 实际{actual_tool['parsed_arguments']}")

                        error_msg = f"工具 {k+1} 验证失败: {'; '.join(error_details)}"
                        print(f"  ❌ {error_msg}")
                        result.add_fail(error_msg)
                else:
                    error_msg = f"缺少工具 {k+1}: {expected_tool['name']}"
                    print(f"  ❌ {error_msg}")
                    result.add_fail(error_msg)

            # 显示提取的工具详情
            if extracted_tools:
                print(f"\n🔍 提取的工具详情:")
                for tool in extracted_tools:
                    print(f"  - {tool['name']}(id={tool['id']})")
                    print(f"    参数: {tool['parsed_arguments']}")

        except Exception as e:
            error_msg = f"测试 {scenario['name']} 执行失败: {str(e)}"
            print(f"❌ {error_msg}")
            result.add_fail(error_msg)
            logger.error(f"测试执行异常: {e}")

    result.print_summary()
    return result


def test_edge_cases():
    """测试边界情况和异常处理"""

    result = TestResult("边界情况测试")

    edge_cases = [
        {
            "name": "空内容处理",
            "data": {"edit_index": 0, "edit_content": "", "phase": "tool_call"},
            "should_pass": True
        },
        {
            "name": "无效JSON处理",
            "data": {"edit_index": 0, "edit_content": '<glm_block >{"invalid": json}}</glm_block>', "phase": "tool_call"},
            "should_pass": True  # 应该优雅处理，不崩溃
        },
        {
            "name": "不完整的glm_block",
            "data": {"edit_index": 0, "edit_content": '<glm_block >{"type": "mcp", "data": {"metadata": {"id": "test"', "phase": "tool_call"},
            "should_pass": True
        },
        {
            "name": "超大edit_index",
            "data": {"edit_index": 999999, "edit_content": "test", "phase": "tool_call"},
            "should_pass": True
        },
        {
            "name": "特殊字符处理",
            "data": {"edit_index": 0, "edit_content": '<glm_block >{"type": "mcp", "data": {"metadata": {"id": "test", "name": "test", "arguments": "{\\"text\\":\\"测试\\u4e2d\\u6587\\"}"}}}</glm_block>', "phase": "tool_call"},
            "should_pass": True
        }
    ]

    print(f"\n🧪 开始执行 {len(edge_cases)} 个边界情况测试...")

    for i, case in enumerate(edge_cases, 1):
        print(f"\n📦 测试 {i}: {case['name']}")

        try:
            handler = SSEToolHandler("test_chat_id", "GLM-4.5")

            # 处理数据
            if case["data"]["phase"] == "tool_call":
                chunks = list(handler.process_tool_call_phase(case["data"], is_stream=True))
            else:
                chunks = list(handler.process_other_phase(case["data"], is_stream=True))

            # 检查是否按预期处理
            if case["should_pass"]:
                print(f"  ✅ 成功处理，生成 {len(chunks)} 个输出块")
                result.add_pass()
            else:
                print(f"  ❌ 应该失败但成功了")
                result.add_fail(f"{case['name']}: 应该失败但成功了")

        except Exception as e:
            if case["should_pass"]:
                error_msg = f"{case['name']}: 意外异常 - {str(e)}"
                print(f"  ❌ {error_msg}")
                result.add_fail(error_msg)
            else:
                print(f"  ✅ 按预期失败: {str(e)}")
                result.add_pass()

    result.print_summary()
    return result


def test_performance():
    """测试性能表现"""

    result = TestResult("性能测试")

    print(f"\n🚀 开始性能测试...")

    # 测试大量小块数据的处理性能
    handler = SSEToolHandler("test_chat_id", "GLM-4.5")

    start_time = time.time()

    # 模拟1000次小的编辑操作
    for i in range(1000):
        data = {
            "edit_index": i * 5,
            "edit_content": f"chunk_{i}",
            "phase": "tool_call"
        }
        list(handler.process_tool_call_phase(data, is_stream=False))

    end_time = time.time()
    duration = end_time - start_time

    print(f"⏱️ 处理1000次编辑操作耗时: {duration:.3f}秒")
    print(f"📊 平均每次操作耗时: {duration * 1000 / 1000:.3f}毫秒")

    # 性能基准：每次操作应该在1毫秒以内
    if duration < 1.0:  # 1秒内完成1000次操作
        print("✅ 性能测试通过")
        result.add_pass()
    else:
        error_msg = f"性能测试失败: 耗时{duration:.3f}秒，超过1秒基准"
        print(f"❌ {error_msg}")
        result.add_fail(error_msg)

    result.print_summary()
    return result


def test_argument_parsing():
    """测试参数解析功能"""

    result = TestResult("参数解析测试")

    print(f"\n🧪 开始参数解析测试...")

    handler = SSEToolHandler("test", "test")

    test_cases = [
        ('{"city": "北京"}', {"city": "北京"}),
        ('{"city": "北京', {"city": "北京"}),  # 缺少闭合括号
        ('{"city": "北京"', {"city": "北京"}),  # 缺少闭合括号但有引号
        ('{\\"city\\": \\"北京\\"}', {"city": "北京"}),  # 转义的JSON
        ('{}', {}),  # 空参数
        ('null', {}),  # null参数
        ('{"array": [1,2,3], "nested": {"key": "value"}}', {"array": [1,2,3], "nested": {"key": "value"}}),  # 复杂参数
        ('{"url":"https://www.goo', {"url": "https://www.goo"}),  # 不完整的URL
        ('', {}),  # 空字符串
        ('{', {}),  # 只有开始括号
    ]

    for i, (input_str, expected) in enumerate(test_cases, 1):
        try:
            parsed_result = handler._parse_partial_arguments(input_str)
            success = parsed_result == expected

            if success:
                print(f"✅ 测试 {i}: 解析成功")
                result.add_pass()
            else:
                error_msg = f"测试 {i} 失败: 输入'{input_str[:30]}...', 期望{expected}, 实际{parsed_result}"
                print(f"❌ {error_msg}")
                result.add_fail(error_msg)

        except Exception as e:
            error_msg = f"测试 {i} 异常: 输入'{input_str[:30]}...', 错误: {str(e)}"
            print(f"❌ {error_msg}")
            result.add_fail(error_msg)

    result.print_summary()
    return result


def run_all_tests():
    """运行所有测试"""

    print("🧪 SSE工具调用处理器优化测试套件")
    print("="*60)

    all_results = []

    try:
        # 运行真实场景测试
        print("\n1️⃣ 真实场景测试")
        all_results.append(test_real_world_scenarios())

        # 运行边界情况测试
        print("\n2️⃣ 边界情况测试")
        all_results.append(test_edge_cases())

        # 运行参数解析测试
        print("\n3️⃣ 参数解析测试")
        all_results.append(test_argument_parsing())

        # 运行性能测试
        print("\n4️⃣ 性能测试")
        all_results.append(test_performance())

        # 汇总结果
        print("\n" + "="*60)
        print("📊 测试汇总")
        print("="*60)

        total_passed = sum(r.passed for r in all_results)
        total_failed = sum(r.failed for r in all_results)
        total_tests = total_passed + total_failed

        print(f"总测试数: {total_tests}")
        print(f"✅ 通过: {total_passed}")
        print(f"❌ 失败: {total_failed}")

        if total_tests > 0:
            success_rate = (total_passed / total_tests) * 100
            print(f"📈 总体成功率: {success_rate:.1f}%")

            if success_rate >= 90:
                print("🎉 测试结果优秀！")
            elif success_rate >= 70:
                print("👍 测试结果良好")
            else:
                print("⚠️ 需要改进")

        # 显示失败的测试
        failed_tests = []
        for result in all_results:
            failed_tests.extend(result.errors)

        if failed_tests:
            print(f"\n🔍 失败测试详情:")
            for i, error in enumerate(failed_tests, 1):
                print(f"  {i}. {error}")

        return total_failed == 0

    except Exception as e:
        print(f"❌ 测试套件执行失败: {e}")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)