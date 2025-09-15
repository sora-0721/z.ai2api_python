#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from typing import Dict, List, Optional
from pydantic_settings import BaseSettings
from app.utils.logger import logger


class Settings(BaseSettings):
    """Application settings"""

    # API Configuration
    API_ENDPOINT: str = os.getenv("API_ENDPOINT", "https://chat.z.ai/api/chat/completions")
    AUTH_TOKEN: str = os.getenv("AUTH_TOKEN", "sk-your-api-key")

    # 认证token文件路径
    AUTH_TOKENS_FILE: str = os.getenv("AUTH_TOKENS_FILE", "tokens.txt")

    # Token池配置
    TOKEN_HEALTH_CHECK_INTERVAL: int = int(os.getenv("TOKEN_HEALTH_CHECK_INTERVAL", "300"))  # 5分钟
    TOKEN_FAILURE_THRESHOLD: int = int(os.getenv("TOKEN_FAILURE_THRESHOLD", "3"))  # 失败3次后标记为不可用
    TOKEN_RECOVERY_TIMEOUT: int = int(os.getenv("TOKEN_RECOVERY_TIMEOUT", "1800"))  # 30分钟后重试失败的token

    def _load_tokens_from_file(self, file_path: str) -> List[str]:
        """
        从文件加载token列表

        支持两种格式：
        1. 每行一个token（原格式）
        2. 逗号分隔的token（新格式）

        处理规则：
        - 跳过空行和注释行（以#开头）
        - 自动检测并处理逗号分隔格式
        - 去除空格和换行符
        """
        tokens = []
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()

                    if not content:
                        logger.debug(f"📄 Token文件为空: {file_path}")
                        return tokens

                    # 检查是否包含逗号分隔格式
                    if ',' in content:
                        # 逗号分隔格式：将整个文件内容按逗号分割
                        logger.debug(f"📄 检测到逗号分隔格式: {file_path}")

                        # 移除注释行后再分割
                        lines = content.split('\n')
                        clean_content = []
                        for line in lines:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                clean_content.append(line)

                        # 合并所有非注释内容，然后按逗号分割
                        merged_content = ' '.join(clean_content)
                        raw_tokens = merged_content.split(',')

                        for token in raw_tokens:
                            token = token.strip()
                            if token:  # 跳过空token
                                tokens.append(token)
                    else:
                        # 每行一个token格式（原格式）
                        logger.debug(f"📄 使用每行一个token格式: {file_path}")
                        for line in content.split('\n'):
                            line = line.strip()
                            # 跳过空行和注释行
                            if line and not line.startswith('#'):
                                tokens.append(line)

                logger.info(f"📄 从文件加载了 {len(tokens)} 个token: {file_path}")
            else:
                logger.debug(f"📄 Token文件不存在: {file_path}")
        except Exception as e:
            logger.error(f"❌ 读取token文件失败 {file_path}: {e}")
        return tokens

    @property
    def auth_token_list(self) -> List[str]:
        """
        解析认证token列表

        仅从AUTH_TOKENS_FILE指定的文件加载token
        """
        # 从文件加载token
        tokens = self._load_tokens_from_file(self.AUTH_TOKENS_FILE)

        # 去重，保持顺序
        if tokens:
            seen = set()
            unique_tokens = []
            for token in tokens:
                if token not in seen:
                    unique_tokens.append(token)
                    seen.add(token)

            # 记录去重信息
            duplicate_count = len(tokens) - len(unique_tokens)
            if duplicate_count > 0:
                logger.warning(f"⚠️ 检测到 {duplicate_count} 个重复token，已自动去重")

            return unique_tokens

        return []

    # Model Configuration
    PRIMARY_MODEL: str = os.getenv("PRIMARY_MODEL", "GLM-4.5")
    THINKING_MODEL: str = os.getenv("THINKING_MODEL", "GLM-4.5-Thinking")
    SEARCH_MODEL: str = os.getenv("SEARCH_MODEL", "GLM-4.5-Search")
    AIR_MODEL: str = os.getenv("AIR_MODEL", "GLM-4.5-Air")

    # Server Configuration
    LISTEN_PORT: int = int(os.getenv("LISTEN_PORT", "8080"))
    DEBUG_LOGGING: bool = os.getenv("DEBUG_LOGGING", "true").lower() == "true"

    ANONYMOUS_MODE: bool = os.getenv("ANONYMOUS_MODE", "true").lower() == "true"
    TOOL_SUPPORT: bool = os.getenv("TOOL_SUPPORT", "true").lower() == "true"
    SCAN_LIMIT: int = int(os.getenv("SCAN_LIMIT", "200000"))
    SKIP_AUTH_TOKEN: bool = os.getenv("SKIP_AUTH_TOKEN", "false").lower() == "true"

    # Retry Configuration
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "5"))
    RETRY_DELAY: float = float(os.getenv("RETRY_DELAY", "1.0"))  # 初始重试延迟（秒）
    RETRY_BACKOFF: float = float(os.getenv("RETRY_BACKOFF", "2.0"))  # 退避系数

    # Browser Headers
    CLIENT_HEADERS: Dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0",
        "Accept-Language": "zh-CN",
        "sec-ch-ua": '"Not;A=Brand";v="99", "Microsoft Edge";v="139", "Chromium";v="139"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "X-FE-Version": "prod-fe-1.0.70",
        "Origin": "https://chat.z.ai",
    }

    class Config:
        env_file = ".env"


settings = Settings()
