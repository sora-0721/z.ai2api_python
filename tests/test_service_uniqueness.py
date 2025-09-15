#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试服务唯一性验证功能
"""

import time
import subprocess
import sys
from pathlib import Path

from app.core.config import settings
from app.utils.process_manager import ProcessManager, ensure_service_uniqueness
from app.utils.logger import setup_logger

# 设置日志
logger = setup_logger(log_dir="logs", debug_mode=True)


def test_process_manager():
    """测试进程管理器功能"""
    print("=" * 60)
    print("测试进程管理器功能")
    print("=" * 60)
    
    service_name = "test-z-ai2api-server"
    port = 8081
    
    # 创建进程管理器
    manager = ProcessManager(service_name=service_name, port=port)
    
    print(f"\n1. 测试服务唯一性检查...")
    print(f"   服务名称: {service_name}")
    print(f"   端口: {port}")
    
    # 第一次检查应该通过
    result1 = manager.check_service_uniqueness()
    print(f"   第一次检查结果: {'✅ 通过' if result1 else '❌ 失败'}")
    
    if result1:
        # 创建 PID 文件
        manager.create_pid_file()
        print(f"   已创建 PID 文件: {manager.pid_file}")
        
        # 第二次检查应该失败（因为 PID 文件存在且进程运行中）
        manager2 = ProcessManager(service_name=service_name, port=port)
        result2 = manager2.check_service_uniqueness()
        print(f"   第二次检查结果: {'✅ 通过' if result2 else '❌ 失败（预期）'}")
        
        # 清理
        manager.cleanup_on_exit()
        print(f"   已清理 PID 文件")
        
        # 第三次检查应该通过
        manager3 = ProcessManager(service_name=service_name, port=port)
        result3 = manager3.check_service_uniqueness()
        print(f"   第三次检查结果: {'✅ 通过' if result3 else '❌ 失败'}")


def test_convenience_function():
    """测试便捷函数"""
    print("\n" + "=" * 60)
    print("测试便捷函数")
    print("=" * 60)
    
    service_name = "test-convenience-server"
    port = 8082
    
    print(f"\n2. 测试便捷函数...")
    print(f"   服务名称: {service_name}")
    print(f"   端口: {port}")
    
    # 第一次调用应该成功
    result1 = ensure_service_uniqueness(service_name=service_name, port=port)
    print(f"   第一次调用结果: {'✅ 成功' if result1 else '❌ 失败'}")
    
    if result1:
        # 第二次调用应该失败
        result2 = ensure_service_uniqueness(service_name=service_name, port=port)
        print(f"   第二次调用结果: {'✅ 成功' if result2 else '❌ 失败（预期）'}")
        
        # 手动清理
        pid_file = Path(f"{service_name}.pid")
        if pid_file.exists():
            pid_file.unlink()
            print(f"   已手动清理 PID 文件")


def test_real_service():
    """测试真实服务场景"""
    print("\n" + "=" * 60)
    print("测试真实服务场景")
    print("=" * 60)
    
    service_name = settings.SERVICE_NAME
    port = settings.LISTEN_PORT
    
    print(f"\n3. 测试真实服务场景...")
    print(f"   服务名称: {service_name}")
    print(f"   端口: {port}")
    
    # 检查当前是否有服务运行
    manager = ProcessManager(service_name=service_name, port=port)
    instances = manager.get_running_instances()
    
    if instances:
        print(f"   发现 {len(instances)} 个运行中的实例:")
        for instance in instances:
            print(f"     PID: {instance['pid']}, 启动时间: {instance['start_time']}")
    else:
        print("   未发现运行中的实例")
    
    # 测试唯一性检查
    result = manager.check_service_uniqueness()
    print(f"   唯一性检查结果: {'✅ 可以启动' if result else '❌ 已有实例运行'}")


def test_port_conflict():
    """测试端口冲突检测"""
    print("\n" + "=" * 60)
    print("测试端口冲突检测")
    print("=" * 60)
    
    print(f"\n4. 测试端口冲突检测...")
    
    # 尝试检测一些常用端口
    test_ports = [80, 443, 8080, 3000, 5000]
    
    for port in test_ports:
        manager = ProcessManager(service_name="test-port-check", port=port)
        is_occupied = manager._check_port_usage()
        print(f"   端口 {port}: {'❌ 被占用' if is_occupied else '✅ 可用'}")


def main():
    """主测试函数"""
    print("🧪 Z.AI2API 服务唯一性验证测试")
    print("=" * 60)
    print("此测试将验证以下功能:")
    print("1. 进程管理器基本功能")
    print("2. 便捷函数功能")
    print("3. 真实服务场景")
    print("4. 端口冲突检测")
    print("=" * 60)
    
    try:
        # 运行所有测试
        test_process_manager()
        test_convenience_function()
        test_real_service()
        test_port_conflict()
        
        print("\n" + "=" * 60)
        print("✅ 所有测试完成")
        print("=" * 60)
        
        print("\n📋 使用说明:")
        print("1. 启动服务时会自动进行唯一性检查")
        print("2. 如果检测到已有实例运行，新实例将拒绝启动")
        print("3. 可以通过环境变量 SERVICE_NAME 自定义服务名称")
        print("4. PID 文件会在服务正常退出时自动清理")
        print("5. 异常退出的 PID 文件会在下次启动时自动清理")
        
    except Exception as e:
        logger.error(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
