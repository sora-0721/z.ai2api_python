#!/usr/bin/env python3
"""
测试 edit_index 重复处理修复
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.sse_tool_handler import SSEToolHandler

def test_edit_index_deduplication():
    """测试 edit_index 去重功能"""
    
    handler = SSEToolHandler("test-model", stream=False)
    
    print("🧪 测试 edit_index 去重功能\n")
    
    # 模拟重复的数据块（相同的 edit_index）
    test_chunks = [
        {
            "phase": "tool_call",
            "edit_content": '<glm_block view="">{"type": "mcp", "data": {"metadata": {"id": "call_test1", "name": "test_tool", "arguments": "{\\"url\\":\\"https://example.com\\"}", "result": "", "display_result": "", "duration": "...", "status": "completed", "is_error": false, "mcp_server": {"name": "mcp-server"}}, "thought": null, "ppt": null, "browser": null}}</glm_block>',
            "edit_index": 100
        },
        {
            "phase": "tool_call", 
            "edit_content": 'some additional content',
            "edit_index": 100  # 相同的 edit_index，应该被跳过
        },
        {
            "phase": "tool_call",
            "edit_content": 'new content with different index',
            "edit_index": 200  # 新的 edit_index，应该被处理
        },
        {
            "phase": "tool_call",
            "edit_content": 'old content',
            "edit_index": 150  # 较小的 edit_index，应该被跳过
        }
    ]
    
    processed_indices = []
    skipped_indices = []

    for i, chunk in enumerate(test_chunks, 1):
        print(f"测试块 {i}: edit_index={chunk['edit_index']}")

        # 记录处理前的状态
        old_index = handler.last_processed_edit_index

        # 处理块
        results = list(handler.process_sse_chunk(chunk))

        # 检查是否实际处理了（通过 last_processed_edit_index 的变化判断）
        if handler.last_processed_edit_index != old_index:
            processed_indices.append(chunk['edit_index'])
            print(f"  ✅ 已处理 (edit_index 更新: {old_index} → {handler.last_processed_edit_index})")
        else:
            skipped_indices.append(chunk['edit_index'])
            print(f"  ⏭️ 已跳过 (edit_index 未变化: {handler.last_processed_edit_index})")

        print(f"  当前 last_processed_edit_index: {handler.last_processed_edit_index}")
        print()

    print(f"📊 测试结果:")
    print(f"  处理的 edit_index: {processed_indices}")
    print(f"  跳过的 edit_index: {skipped_indices}")
    print(f"  最终 last_processed_edit_index: {handler.last_processed_edit_index}")

    # 验证预期结果
    expected_processed = [100, 200]  # 应该只处理 edit_index 100 和 200
    expected_skipped = [100, 150]    # 应该跳过重复的 100 和较小的 150

    if processed_indices == expected_processed and skipped_indices == expected_skipped:
        print("✅ 测试通过！edit_index 去重功能正常工作")
        return True
    else:
        print(f"❌ 测试失败！")
        print(f"  期望处理: {expected_processed}, 实际处理: {processed_indices}")
        print(f"  期望跳过: {expected_skipped}, 实际跳过: {skipped_indices}")
        return False

def test_reset_functionality():
    """测试重置功能"""
    
    print("\n🧪 测试重置功能\n")
    
    handler = SSEToolHandler("test-model", stream=False)
    
    # 处理一个块
    chunk = {
        "phase": "tool_call",
        "edit_content": "test content",
        "edit_index": 500
    }
    
    list(handler.process_sse_chunk(chunk))
    print(f"处理后 last_processed_edit_index: {handler.last_processed_edit_index}")
    
    # 重置状态
    handler._reset_all_state()
    print(f"重置后 last_processed_edit_index: {handler.last_processed_edit_index}")
    
    # 验证重置是否正确
    if handler.last_processed_edit_index == -1:
        print("✅ 重置功能正常工作")
        return True
    else:
        print("❌ 重置功能异常")
        return False

if __name__ == "__main__":
    test1_passed = test_edit_index_deduplication()
    test2_passed = test_reset_functionality()
    
    print(f"\n🎯 总体测试结果:")
    if test1_passed and test2_passed:
        print("✅ 所有测试通过！edit_index 重复处理问题已修复")
    else:
        print("❌ 部分测试失败，需要进一步调试")
