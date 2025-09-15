#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
进程管理模块
提供服务唯一性验证和进程管理功能
"""

import os
import sys
import time
import psutil
from typing import Optional, List
from pathlib import Path

from app.utils.logger import get_logger

logger = get_logger()


class ProcessManager:
    """进程管理器 - 负责服务唯一性验证和进程管理"""
    
    def __init__(self, service_name: str = "z-ai2api-server", port: int = 8080):
        """
        初始化进程管理器
        
        Args:
            service_name: 服务名称，用于进程名称标识
            port: 服务端口，用于唯一性检查
        """
        self.service_name = service_name
        self.port = port
        self.current_pid = os.getpid()
        self.pid_file = Path(f"{service_name}.pid")
        
    def check_service_uniqueness(self) -> bool:
        """
        检查服务唯一性

        通过以下方式验证：
        1. 检查 PID 文件
        2. 检查端口是否被占用
        3. 检查进程名称 (pname) 是否已存在（可选）

        Returns:
            bool: True 表示可以启动服务，False 表示已有实例运行
        """
        logger.info(f"🔍 检查服务唯一性: {self.service_name} (端口: {self.port})")

        # 1. 优先检查 PID 文件（最可靠）
        if self._check_pid_file():
            return False

        # 2. 检查端口占用
        if self._check_port_usage():
            return False

        # 3. 检查进程名称（作为额外保障）
        if self._check_process_by_name():
            return False

        logger.info("✅ 服务唯一性检查通过，可以启动服务")
        return True
    
    def _check_process_by_name(self) -> bool:
        """
        通过进程名称检查是否已有实例运行

        这是一个保守的检查，只检查明确的服务进程标识

        Returns:
            bool: True 表示发现同名进程，False 表示未发现
        """
        try:
            running_processes = []

            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    proc_info = proc.info

                    # 跳过当前进程
                    if proc_info['pid'] == self.current_pid:
                        continue

                    # 只检查进程名称直接匹配服务名称的情况
                    # 这通常发生在使用 Granian 的 process_name 参数时
                    if proc_info['name'] and proc_info['name'] == self.service_name:
                        running_processes.append(proc_info)
                        continue

                    # 检查命令行参数中是否包含明确的服务标识
                    cmdline = proc_info.get('cmdline', [])
                    if cmdline and len(cmdline) >= 2:
                        cmdline_str = ' '.join(cmdline)

                        # 只检查通过 Granian 启动且明确指定了进程名称的服务
                        if (f'--process-name={self.service_name}' in cmdline_str or
                            f'process_name={self.service_name}' in cmdline_str):
                            running_processes.append(proc_info)

                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    # 进程可能已经结束或无权限访问
                    continue

            if running_processes:
                logger.warning(f"⚠️ 发现 {len(running_processes)} 个同名进程正在运行:")
                for proc_info in running_processes:
                    cmdline = proc_info.get('cmdline', [])
                    cmdline_preview = ' '.join(cmdline[:3]) + '...' if len(cmdline) > 3 else ' '.join(cmdline)
                    logger.warning(f"   PID: {proc_info['pid']}, 名称: {proc_info['name']}, 命令: {cmdline_preview}")
                logger.warning(f"❌ 服务 {self.service_name} 已在运行，请先停止现有实例")
                return True

            return False

        except Exception as e:
            logger.error(f"❌ 检查进程名称时发生错误: {e}")
            return False
    
    def _check_port_usage(self) -> bool:
        """
        检查端口是否被占用
        
        Returns:
            bool: True 表示端口被占用，False 表示端口可用
        """
        try:
            # 获取所有网络连接
            connections = psutil.net_connections(kind='inet')
            
            for conn in connections:
                if (conn.laddr.port == self.port and 
                    conn.status in [psutil.CONN_LISTEN, psutil.CONN_ESTABLISHED]):
                    
                    # 尝试获取占用端口的进程信息
                    try:
                        proc = psutil.Process(conn.pid) if conn.pid else None
                        proc_name = proc.name() if proc else "未知进程"
                        logger.warning(f"⚠️ 端口 {self.port} 已被占用")
                        logger.warning(f"   占用进程: PID {conn.pid}, 名称: {proc_name}")
                        logger.warning(f"❌ 无法启动服务，端口 {self.port} 不可用")
                        return True
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        logger.warning(f"⚠️ 端口 {self.port} 已被占用（无法获取进程信息）")
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ 检查端口占用时发生错误: {e}")
            return False
    
    def _check_pid_file(self) -> bool:
        """
        检查 PID 文件
        
        Returns:
            bool: True 表示发现有效的 PID 文件，False 表示无冲突
        """
        try:
            if not self.pid_file.exists():
                return False
            
            # 读取 PID 文件
            pid_content = self.pid_file.read_text().strip()
            if not pid_content.isdigit():
                logger.warning(f"⚠️ PID 文件格式无效: {self.pid_file}")
                self._cleanup_pid_file()
                return False
            
            old_pid = int(pid_content)
            
            # 检查进程是否仍在运行
            try:
                proc = psutil.Process(old_pid)
                if proc.is_running():
                    logger.warning(f"⚠️ 发现有效的 PID 文件: {self.pid_file}")
                    logger.warning(f"   进程 PID {old_pid} 仍在运行: {proc.name()}")
                    logger.warning(f"❌ 服务可能已在运行，请检查进程或删除 PID 文件")
                    return True
                else:
                    logger.info(f"🧹 清理无效的 PID 文件: {self.pid_file}")
                    self._cleanup_pid_file()
                    return False
            except psutil.NoSuchProcess:
                logger.info(f"🧹 清理过期的 PID 文件: {self.pid_file}")
                self._cleanup_pid_file()
                return False
                
        except Exception as e:
            logger.error(f"❌ 检查 PID 文件时发生错误: {e}")
            return False
    
    def _cleanup_pid_file(self):
        """清理 PID 文件"""
        try:
            if self.pid_file.exists():
                self.pid_file.unlink()
                logger.debug(f"🧹 已删除 PID 文件: {self.pid_file}")
        except Exception as e:
            logger.error(f"❌ 删除 PID 文件失败: {e}")
    
    def create_pid_file(self):
        """创建 PID 文件"""
        try:
            self.pid_file.write_text(str(self.current_pid))
            logger.info(f"📝 创建 PID 文件: {self.pid_file} (PID: {self.current_pid})")
        except Exception as e:
            logger.error(f"❌ 创建 PID 文件失败: {e}")
    
    def cleanup_on_exit(self):
        """退出时清理资源"""
        logger.info(f"🧹 清理进程资源 (PID: {self.current_pid})")
        self._cleanup_pid_file()
    
    def get_running_instances(self) -> List[dict]:
        """
        获取所有运行中的服务实例

        Returns:
            List[dict]: 运行中的实例信息列表
        """
        instances = []

        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
                try:
                    proc_info = proc.info

                    # 跳过当前进程
                    if proc_info['pid'] == self.current_pid:
                        continue

                    # 使用与 _check_process_by_name 相同的保守逻辑
                    is_service = False

                    # 只检查进程名称直接匹配服务名称的情况
                    if proc_info['name'] and proc_info['name'] == self.service_name:
                        is_service = True

                    # 检查命令行参数中是否包含明确的服务标识
                    cmdline = proc_info.get('cmdline', [])
                    if cmdline and len(cmdline) >= 2:
                        cmdline_str = ' '.join(cmdline)

                        # 只检查通过 Granian 启动且明确指定了进程名称的服务
                        if (f'--process-name={self.service_name}' in cmdline_str or
                            f'process_name={self.service_name}' in cmdline_str):
                            is_service = True

                    if is_service:
                        instances.append({
                            'pid': proc_info['pid'],
                            'name': proc_info['name'],
                            'cmdline': cmdline,
                            'create_time': proc_info['create_time'],
                            'start_time': time.strftime('%Y-%m-%d %H:%M:%S',
                                                      time.localtime(proc_info['create_time']))
                        })

                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue

        except Exception as e:
            logger.error(f"❌ 获取运行实例时发生错误: {e}")

        return instances


def ensure_service_uniqueness(service_name: str = "z-ai2api-server", port: int = 8080) -> bool:
    """
    确保服务唯一性的便捷函数
    
    Args:
        service_name: 服务名称
        port: 服务端口
        
    Returns:
        bool: True 表示可以启动，False 表示应该退出
    """
    manager = ProcessManager(service_name, port)
    
    if not manager.check_service_uniqueness():
        logger.error("❌ 服务唯一性检查失败，程序退出")
        
        # 显示运行中的实例
        instances = manager.get_running_instances()
        if instances:
            logger.info("📋 当前运行的实例:")
            for instance in instances:
                logger.info(f"   PID: {instance['pid']}, 启动时间: {instance['start_time']}")
        
        return False
    
    # 创建 PID 文件
    manager.create_pid_file()
    
    # 注册退出清理
    import atexit
    atexit.register(manager.cleanup_on_exit)
    
    return True
