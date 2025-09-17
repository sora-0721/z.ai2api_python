#!/usr/bin/env python3
"""
测试引号问题
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.sse_tool_handler import SSEToolHandler

def test_quote_issue():
    """测试引号问题"""

    handler = SSEToolHandler("test-model", stream=False)

    # 从日志中提取的原始问题数据
    test_data = '{"command":"echo \\"添加更多内容\\uff1a$(date)\\\\\\" >> \\\\\\"C:\\\\\\\\Users\\\\\\\\cassianvale\\\\\\\\Documents\\\\\\\\GitHub\\\\\\\\z.ai2api_python\\\\\\\\1.txt\\\\\\"\\"","description":"\\u54111.txt\\u6587\\u4ef6\\u6dfb\\u52a0\\u5f53\\u524d\\u65f6\\u95f4\\u6233\\u5185\\u5bb9"}'

    print("🔍 测试引号问题")
    print(f"原始输入: {test_data}")
    print()

    try:
        result_str = handler._fix_tool_arguments(test_data)
        print(f"修复结果字符串: {result_str}")

        # 解析修复后的JSON
        import json
        result = json.loads(result_str)

        # 检查命令是否有语法问题
        if 'command' in result:
            command = result['command']
            print(f"命令: {command}")

            # 检查是否有多余的引号
            if command.endswith('""'):
                print("❌ 发现多余的引号！")
                print("需要修复这个问题")
            else:
                print("✅ 引号正常")

    except Exception as e:
        print(f"❌ 修复失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_quote_issue()
