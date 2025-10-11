#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试删除 Token 时 token_stats 表的级联删除

验证修复：
1. 删除 token 时，对应的 token_stats 记录也应被删除
2. 外键约束正常工作
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

from app.services.token_dao import get_token_dao
from app.utils.logger import logger


async def test_cascade_delete():
    """测试级联删除"""
    print("\n" + "=" * 60)
    print("测试 Token 级联删除")
    print("=" * 60)

    dao = get_token_dao()
    await dao.init_database()

    # 步骤 1: 添加测试 Token
    print("\n[步骤 1] 添加测试 Token...")
    test_token = "cascade_delete_test_token_12345"
    token_id = await dao.add_token("zai", test_token, token_type="user", validate=False)

    if not token_id:
        print("❌ 测试失败：Token 添加失败")
        return False

    print(f"✅ Token 已添加: ID={token_id}")

    # 步骤 2: 验证 token_stats 记录存在
    print("\n[步骤 2] 验证 token_stats 记录...")
    stats = await dao.get_token_stats(token_id)

    if not stats:
        print("❌ 测试失败：token_stats 记录不存在")
        await dao.delete_token(token_id)
        return False

    print(f"✅ token_stats 记录存在: ID={stats['id']}")

    # 步骤 3: 删除 Token
    print("\n[步骤 3] 删除 Token...")
    await dao.delete_token(token_id)
    print(f"✅ Token 已删除: ID={token_id}")

    # 步骤 4: 验证 token_stats 记录被级联删除
    print("\n[步骤 4] 验证 token_stats 级联删除...")
    stats_after = await dao.get_token_stats(token_id)

    if stats_after:
        print(f"❌ 测试失败：token_stats 记录仍然存在: {stats_after}")
        return False

    print("✅ token_stats 记录已被级联删除")

    # 步骤 5: 验证 Token 确实被删除
    print("\n[步骤 5] 验证 Token 已删除...")
    token_info = await dao.get_token_by_value("zai", test_token)

    if token_info:
        print(f"❌ 测试失败：Token 记录仍然存在: {token_info}")
        return False

    print("✅ Token 记录已被删除")

    return True


async def test_foreign_key_enabled():
    """测试外键约束是否启用"""
    print("\n" + "=" * 60)
    print("测试外键约束是否启用")
    print("=" * 60)

    dao = get_token_dao()

    async with dao.get_connection() as conn:
        cursor = await conn.execute("PRAGMA foreign_keys")
        row = await cursor.fetchone()
        fk_enabled = row[0] if row else 0

    print(f"\n外键约束状态: {'启用' if fk_enabled else '禁用'}")

    if fk_enabled:
        print("✅ 外键约束已启用")
        return True
    else:
        print("❌ 外键约束未启用")
        return False


async def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Token 级联删除测试套件")
    print("=" * 60)

    try:
        # 测试 1: 外键约束
        fk_test = await test_foreign_key_enabled()

        # 测试 2: 级联删除
        cascade_test = await test_cascade_delete()

        print("\n" + "=" * 60)
        if fk_test and cascade_test:
            print("✅ 所有测试通过！")
            print("=" * 60)
            return 0
        else:
            print("❌ 部分测试失败")
            print("=" * 60)
            return 1

    except Exception as e:
        print("\n" + "=" * 60)
        print(f"💥 测试异常: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
