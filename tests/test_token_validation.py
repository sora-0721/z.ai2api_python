#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Token 验证逻辑测试

测试目标：
1. 验证 guest token 被正确拒绝
2. 验证 user token 被正确接受
3. 验证无效 token 被正确拒绝
4. 验证 TokenDAO 集成
"""

import asyncio
import sys
import io
from pathlib import Path

# 设置 UTF-8 输出（Windows 兼容）
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# 添加项目根目录到 sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.utils.token_pool import ZAITokenValidator
from app.services.token_dao import get_token_dao
from app.utils.logger import logger


async def test_token_validator():
    """测试 ZAITokenValidator"""
    print("\n" + "=" * 60)
    print("测试 1: ZAITokenValidator - Token 类型识别")
    print("=" * 60)

    # 测试 1: 无效 Token（随机字符串）
    print("\n[测试 1.1] 无效 Token")
    invalid_token = "invalid_token_string"
    token_type, is_valid, error_msg = await ZAITokenValidator.validate_token(invalid_token)
    print(f"Token: {invalid_token[:20]}...")
    print(f"类型: {token_type}, 有效: {is_valid}, 错误: {error_msg}")
    assert token_type in ["guest", "unknown"], f"预期 unknown 或 guest，实际 {token_type}"
    assert not is_valid, "无效 Token 应该返回 False"
    print("✅ 测试通过")

    # 测试 2: 空 Token
    print("\n[测试 1.2] 空 Token")
    empty_token = ""
    token_type, is_valid, error_msg = await ZAITokenValidator.validate_token(empty_token)
    print(f"类型: {token_type}, 有效: {is_valid}, 错误: {error_msg}")
    assert not is_valid, "空 Token 应该返回 False"
    print("✅ 测试通过")

    print("\n提示: 如需测试真实 Token，请手动替换以下代码中的 Token 并运行")
    print("# real_user_token = 'eyJhbGc...'  # 替换为真实的 user token")
    print("# real_guest_token = 'eyJhbGc...'  # 替换为真实的 guest token")


async def test_token_dao_integration():
    """测试 TokenDAO 与验证逻辑集成"""
    print("\n" + "=" * 60)
    print("测试 2: TokenDAO - 添加 Token 验证")
    print("=" * 60)

    dao = get_token_dao()
    await dao.init_database()

    # 测试 1: 添加无效 Token（应被拒绝）
    print("\n[测试 2.1] 添加无效 Token（预期拒绝）")
    invalid_token = "invalid_test_token_12345"
    token_id = await dao.add_token("zai", invalid_token, validate=True)
    print(f"Token ID: {token_id}")
    assert token_id is None, "无效 Token 不应被添加"
    print("✅ 测试通过 - 无效 Token 被正确拒绝")

    # 测试 2: 添加不验证的 Token（应被接受）
    print("\n[测试 2.2] 添加 Token（跳过验证）")
    test_token = "test_token_no_validation"
    token_id = await dao.add_token("zai", test_token, validate=False)
    print(f"Token ID: {token_id}")
    assert token_id is not None, "跳过验证的 Token 应被添加"
    print("✅ 测试通过 - Token 已添加")

    # 清理测试数据
    if token_id:
        await dao.delete_token(token_id)
        print("✅ 测试数据已清理")

    # 测试 3: 批量添加 Token
    print("\n[测试 2.3] 批量添加 Token（带验证）")
    test_tokens = [
        "invalid_token_1",
        "invalid_token_2",
        "invalid_token_3"
    ]
    added_count, failed_count = await dao.bulk_add_tokens(
        "zai",
        test_tokens,
        validate=True
    )
    print(f"添加成功: {added_count}, 失败: {failed_count}")
    assert failed_count == len(test_tokens), "所有无效 Token 应被拒绝"
    print("✅ 测试通过 - 批量验证正常工作")


async def test_token_type_update():
    """测试 Token 类型更新"""
    print("\n" + "=" * 60)
    print("测试 3: TokenDAO - Token 类型更新")
    print("=" * 60)

    dao = get_token_dao()

    # 添加测试 Token（跳过验证）
    print("\n[测试 3.1] 添加测试 Token")
    test_token = "test_token_for_type_update"
    token_id = await dao.add_token("zai", test_token, token_type="unknown", validate=False)
    assert token_id is not None, "Token 应被添加"
    print(f"✅ Token 已添加: ID={token_id}")

    # 更新 Token 类型
    print("\n[测试 3.2] 更新 Token 类型")
    await dao.update_token_type(token_id, "user")
    print("✅ Token 类型已更新为 user")

    # 验证更新
    print("\n[测试 3.3] 验证更新结果")
    token_info = await dao.get_token_by_value("zai", test_token)
    print(f"Token 类型: {token_info['token_type']}")
    assert token_info["token_type"] == "user", "Token 类型应为 user"
    print("✅ 测试通过 - Token 类型更新成功")

    # 清理测试数据
    await dao.delete_token(token_id)
    print("✅ 测试数据已清理")


async def test_guest_token_rejection_flow():
    """测试完整的 guest token 拒绝流程"""
    print("\n" + "=" * 60)
    print("测试 4: 完整流程 - Guest Token 拒绝")
    print("=" * 60)

    print("\n提示: 此测试需要真实的 guest token 才能完整验证")
    print("如果你有 guest token，请手动替换以下代码中的 token 并运行：")
    print("""
    # 示例代码：
    dao = get_token_dao()
    guest_token = "eyJhbGc..."  # 替换为真实 guest token

    # 尝试添加 guest token
    token_id = await dao.add_token("zai", guest_token, validate=True)

    # 验证结果
    if token_id is None:
        print("✅ Guest token 被正确拒绝")
    else:
        print("❌ Guest token 不应被添加")
        await dao.delete_token(token_id)
    """)

    print("\n⚠️ 跳过此测试（需要真实 guest token）")


async def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Z.AI Token 验证逻辑测试套件")
    print("=" * 60)

    try:
        # 测试 1: Token 验证器
        await test_token_validator()

        # 测试 2: TokenDAO 集成
        await test_token_dao_integration()

        # 测试 3: Token 类型更新
        await test_token_type_update()

        # 测试 4: Guest token 拒绝流程
        await test_guest_token_rejection_flow()

        print("\n" + "=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)

    except AssertionError as e:
        print("\n" + "=" * 60)
        print(f"❌ 测试失败: {e}")
        print("=" * 60)
        sys.exit(1)
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"💥 测试异常: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
