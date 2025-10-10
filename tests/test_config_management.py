#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
配置管理功能测试
"""
import pytest
import asyncio
import os
from app.core.config import settings
from app.admin.api import reload_settings


class TestConfigManagement:
    """配置管理测试套件"""

    def test_config_attributes_exist(self):
        """测试所有配置项是否存在"""
        required_attrs = [
            "SERVICE_NAME",
            "LISTEN_PORT",
            "DEBUG_LOGGING",
            "ANONYMOUS_MODE",
            "AUTH_TOKEN",
            "SKIP_AUTH_TOKEN",
            "TOOL_SUPPORT",
            "TOKEN_FAILURE_THRESHOLD",
            "TOKEN_RECOVERY_TIMEOUT",
            "SCAN_LIMIT",
            "LONGCAT_TOKEN",
        ]

        for attr in required_attrs:
            assert hasattr(settings, attr), f"配置项 {attr} 不存在"
            print(f"✅ {attr}: {getattr(settings, attr)}")

    def test_config_types(self):
        """测试配置项类型"""
        assert isinstance(settings.SERVICE_NAME, str)
        assert isinstance(settings.LISTEN_PORT, int)
        assert isinstance(settings.DEBUG_LOGGING, bool)
        assert isinstance(settings.ANONYMOUS_MODE, bool)
        assert isinstance(settings.SKIP_AUTH_TOKEN, bool)
        assert isinstance(settings.TOOL_SUPPORT, bool)
        assert isinstance(settings.TOKEN_FAILURE_THRESHOLD, int)
        assert isinstance(settings.TOKEN_RECOVERY_TIMEOUT, int)
        assert isinstance(settings.SCAN_LIMIT, int)
        print("✅ 所有配置项类型正确")

    def test_config_default_values(self):
        """测试默认配置值"""
        assert settings.LISTEN_PORT > 0 and settings.LISTEN_PORT < 65536
        assert settings.TOKEN_FAILURE_THRESHOLD > 0
        assert settings.TOKEN_RECOVERY_TIMEOUT > 0
        assert settings.SCAN_LIMIT > 0
        print("✅ 配置默认值合理")

    @pytest.mark.asyncio
    async def test_reload_settings_function(self):
        """测试配置热重载函数"""
        # 记录重载前的值
        old_debug = settings.DEBUG_LOGGING
        old_port = settings.LISTEN_PORT

        # 执行热重载
        success = await reload_settings()

        assert success is True, "配置热重载失败"
        print("✅ 配置热重载成功")

        # 验证配置对象仍然有效
        assert hasattr(settings, "DEBUG_LOGGING")
        assert hasattr(settings, "LISTEN_PORT")

    def test_env_file_exists(self):
        """测试 .env 文件是否存在"""
        assert os.path.exists(".env"), ".env 文件不存在"
        print("✅ .env 文件存在")

    def test_backup_directory_creation(self):
        """测试备份目录创建"""
        backup_dir = "data/backups"
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir, exist_ok=True)

        assert os.path.exists(backup_dir), "备份目录创建失败"
        print(f"✅ 备份目录存在: {backup_dir}")


def test_all():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("配置管理功能测试")
    print("=" * 60 + "\n")

    test = TestConfigManagement()

    # 同步测试
    print("1️⃣ 测试配置项是否存在...")
    test.test_config_attributes_exist()

    print("\n2️⃣ 测试配置项类型...")
    test.test_config_types()

    print("\n3️⃣ 测试配置默认值...")
    test.test_config_default_values()

    print("\n4️⃣ 测试 .env 文件...")
    test.test_env_file_exists()

    print("\n5️⃣ 测试备份目录...")
    test.test_backup_directory_creation()

    # 异步测试
    print("\n6️⃣ 测试配置热重载功能...")
    asyncio.run(test.test_reload_settings_function())

    print("\n" + "=" * 60)
    print("✅ 所有测试通过！")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    test_all()
