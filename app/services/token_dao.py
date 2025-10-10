"""
Token 数据访问层 (DAO)
提供 Token 的 CRUD 操作和查询功能
"""
import aiosqlite
import sqlite3
from typing import List, Optional, Dict, Tuple
from datetime import datetime
from contextlib import asynccontextmanager
import os

from app.models.token_db import SQL_CREATE_TABLES, DB_PATH
from app.utils.logger import logger


class TokenDAO:
    """Token 数据访问对象"""

    def __init__(self, db_path: str = DB_PATH):
        """初始化 DAO"""
        self.db_path = db_path
        self._ensure_db_directory()

    def _ensure_db_directory(self):
        """确保数据库目录存在"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

    @asynccontextmanager
    async def get_connection(self):
        """获取异步数据库连接"""
        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row  # 返回字典式结果

        # 启用外键约束（SQLite 默认关闭）
        await conn.execute("PRAGMA foreign_keys = ON")

        try:
            yield conn
        finally:
            await conn.close()

    def get_sync_connection(self):
        """获取同步数据库连接（用于初始化）"""
        conn = sqlite3.connect(self.db_path)
        # 启用外键约束
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    async def init_database(self):
        """初始化数据库表结构"""
        try:
            # 使用同步连接创建表（避免异步初始化问题）
            conn = self.get_sync_connection()
            conn.executescript(SQL_CREATE_TABLES)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"❌ Token 数据库初始化失败: {e}")
            raise

    # ==================== Token CRUD 操作 ====================

    async def add_token(
        self,
        provider: str,
        token: str,
        token_type: str = "user",
        priority: int = 0,
        validate: bool = True
    ) -> Optional[int]:
        """
        添加新 Token（可选验证）

        Args:
            provider: 提供商名称
            token: Token 值
            token_type: Token 类型（如果 validate=True 将被验证结果覆盖）
            priority: 优先级
            validate: 是否验证 Token（仅针对 zai 提供商）

        Returns:
            token_id 或 None（验证失败或已存在）
        """
        try:
            # 对于 zai 提供商，强制验证 Token
            if provider == "zai" and validate:
                from app.utils.token_pool import ZAITokenValidator

                validated_type, is_valid, error_msg = await ZAITokenValidator.validate_token(token)

                # 拒绝 guest token
                if validated_type == "guest":
                    logger.warning(f"🚫 拒绝添加匿名用户 Token: {token[:20]}... - {error_msg}")
                    return None

                # 拒绝无效 token
                if not is_valid:
                    logger.warning(f"🚫 Token 验证失败: {token[:20]}... - {error_msg}")
                    return None

                # 使用验证后的类型
                token_type = validated_type

            async with self.get_connection() as conn:
                cursor = await conn.execute("""
                    INSERT OR IGNORE INTO tokens (provider, token, token_type, priority)
                    VALUES (?, ?, ?, ?)
                """, (provider, token, token_type, priority))

                await conn.commit()

                if cursor.lastrowid > 0:
                    # 同时创建统计记录
                    await conn.execute("""
                        INSERT INTO token_stats (token_id)
                        VALUES (?)
                    """, (cursor.lastrowid,))
                    await conn.commit()
                    logger.info(f"✅ 添加 Token: {provider} ({token_type}) - {token[:20]}...")
                    return cursor.lastrowid
                else:
                    logger.warning(f"⚠️ Token 已存在: {provider} - {token[:20]}...")
                    return None
        except Exception as e:
            logger.error(f"❌ 添加 Token 失败: {e}")
            return None

    async def get_tokens_by_provider(self, provider: str, enabled_only: bool = True) -> List[Dict]:
        """
        获取指定提供商的所有 Token

        Args:
            provider: 提供商名称
            enabled_only: 是否只返回启用的 Token
        """
        try:
            async with self.get_connection() as conn:
                query = """
                    SELECT t.*, ts.total_requests, ts.successful_requests, ts.failed_requests,
                           ts.last_success_time, ts.last_failure_time
                    FROM tokens t
                    LEFT JOIN token_stats ts ON t.id = ts.token_id
                    WHERE t.provider = ?
                """
                params = [provider]

                if enabled_only:
                    query += " AND t.is_enabled = 1"

                query += " ORDER BY t.priority DESC, t.id ASC"

                cursor = await conn.execute(query, params)
                rows = await cursor.fetchall()

                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"❌ 查询 Token 失败: {e}")
            return []

    async def get_all_tokens(self, enabled_only: bool = False) -> List[Dict]:
        """获取所有 Token"""
        try:
            async with self.get_connection() as conn:
                query = """
                    SELECT t.*, ts.total_requests, ts.successful_requests, ts.failed_requests,
                           ts.last_success_time, ts.last_failure_time
                    FROM tokens t
                    LEFT JOIN token_stats ts ON t.id = ts.token_id
                """

                if enabled_only:
                    query += " WHERE t.is_enabled = 1"

                query += " ORDER BY t.provider, t.priority DESC, t.id ASC"

                cursor = await conn.execute(query)
                rows = await cursor.fetchall()

                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"❌ 查询所有 Token 失败: {e}")
            return []

    async def update_token_status(self, token_id: int, is_enabled: bool):
        """更新 Token 启用状态"""
        try:
            async with self.get_connection() as conn:
                await conn.execute("""
                    UPDATE tokens SET is_enabled = ? WHERE id = ?
                """, (is_enabled, token_id))
                await conn.commit()
                logger.info(f"✅ 更新 Token 状态: id={token_id}, enabled={is_enabled}")
        except Exception as e:
            logger.error(f"❌ 更新 Token 状态失败: {e}")

    async def update_token_type(self, token_id: int, token_type: str):
        """更新 Token 类型"""
        try:
            async with self.get_connection() as conn:
                await conn.execute("""
                    UPDATE tokens SET token_type = ? WHERE id = ?
                """, (token_type, token_id))
                await conn.commit()
                logger.info(f"✅ 更新 Token 类型: id={token_id}, type={token_type}")
        except Exception as e:
            logger.error(f"❌ 更新 Token 类型失败: {e}")

    async def delete_token(self, token_id: int):
        """删除 Token（级联删除统计数据）"""
        try:
            async with self.get_connection() as conn:
                await conn.execute("DELETE FROM tokens WHERE id = ?", (token_id,))
                await conn.commit()
                logger.info(f"✅ 删除 Token: id={token_id}")
        except Exception as e:
            logger.error(f"❌ 删除 Token 失败: {e}")

    async def delete_tokens_by_provider(self, provider: str):
        """删除指定提供商的所有 Token"""
        try:
            async with self.get_connection() as conn:
                await conn.execute("DELETE FROM tokens WHERE provider = ?", (provider,))
                await conn.commit()
                logger.info(f"✅ 删除提供商所有 Token: {provider}")
        except Exception as e:
            logger.error(f"❌ 删除提供商 Token 失败: {e}")

    # ==================== Token 统计操作 ====================

    async def record_success(self, token_id: int):
        """记录 Token 使用成功"""
        try:
            async with self.get_connection() as conn:
                await conn.execute("""
                    UPDATE token_stats
                    SET total_requests = total_requests + 1,
                        successful_requests = successful_requests + 1,
                        last_success_time = CURRENT_TIMESTAMP
                    WHERE token_id = ?
                """, (token_id,))
                await conn.commit()
        except Exception as e:
            logger.error(f"❌ 记录成功失败: {e}")

    async def record_failure(self, token_id: int):
        """记录 Token 使用失败"""
        try:
            async with self.get_connection() as conn:
                await conn.execute("""
                    UPDATE token_stats
                    SET total_requests = total_requests + 1,
                        failed_requests = failed_requests + 1,
                        last_failure_time = CURRENT_TIMESTAMP
                    WHERE token_id = ?
                """, (token_id,))
                await conn.commit()
        except Exception as e:
            logger.error(f"❌ 记录失败失败: {e}")

    async def get_token_stats(self, token_id: int) -> Optional[Dict]:
        """获取 Token 统计信息"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT * FROM token_stats WHERE token_id = ?
                """, (token_id,))
                row = await cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"❌ 获取统计信息失败: {e}")
            return None

    # ==================== 批量操作 ====================

    async def bulk_add_tokens(
        self,
        provider: str,
        tokens: List[str],
        token_type: str = "user",
        validate: bool = True
    ) -> Tuple[int, int]:
        """
        批量添加 Token（可选验证）

        Args:
            provider: 提供商名称
            tokens: Token 列表
            token_type: Token 类型（如果 validate=True 将被覆盖）
            validate: 是否验证 Token（仅针对 zai）

        Returns:
            (成功添加数量, 失败数量)
        """
        added_count = 0
        failed_count = 0

        for token in tokens:
            if token.strip():  # 过滤空 token
                token_id = await self.add_token(
                    provider,
                    token.strip(),
                    token_type,
                    validate=validate
                )
                if token_id:
                    added_count += 1
                else:
                    failed_count += 1

        logger.info(f"✅ 批量添加完成: {provider} - 成功 {added_count}/{len(tokens)}，失败 {failed_count}")
        return added_count, failed_count

    async def replace_tokens(self, provider: str, tokens: List[str],
                            token_type: str = "user"):
        """
        替换指定提供商的所有 Token（先删除后添加）
        """
        # 删除旧 Token
        await self.delete_tokens_by_provider(provider)

        # 添加新 Token
        added_count = await self.bulk_add_tokens(provider, tokens, token_type)

        logger.info(f"✅ 替换 Token 完成: {provider} - {added_count} 个")
        return added_count

    # ==================== 实用方法 ====================

    async def get_token_by_value(self, provider: str, token: str) -> Optional[Dict]:
        """根据 Token 值查询"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT t.*, ts.total_requests, ts.successful_requests, ts.failed_requests
                    FROM tokens t
                    LEFT JOIN token_stats ts ON t.id = ts.token_id
                    WHERE t.provider = ? AND t.token = ?
                """, (provider, token))
                row = await cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"❌ 查询 Token 失败: {e}")
            return None

    async def get_provider_stats(self, provider: str) -> Dict:
        """获取提供商统计信息"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT
                        COUNT(*) as total_tokens,
                        SUM(CASE WHEN is_enabled = 1 THEN 1 ELSE 0 END) as enabled_tokens,
                        SUM(ts.total_requests) as total_requests,
                        SUM(ts.successful_requests) as successful_requests,
                        SUM(ts.failed_requests) as failed_requests
                    FROM tokens t
                    LEFT JOIN token_stats ts ON t.id = ts.token_id
                    WHERE t.provider = ?
                """, (provider,))
                row = await cursor.fetchone()
                return dict(row) if row else {}
        except Exception as e:
            logger.error(f"❌ 获取提供商统计失败: {e}")
            return {}

    # ==================== Token 验证操作 ====================

    async def validate_and_update_token(self, token_id: int) -> bool:
        """
        验证单个 Token 并更新其类型

        Args:
            token_id: Token 数据库 ID

        Returns:
            是否为有效的认证用户 Token
        """
        try:
            # 获取 Token 信息
            async with self.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT provider, token FROM tokens WHERE id = ?
                """, (token_id,))
                row = await cursor.fetchone()

                if not row:
                    logger.error(f"❌ Token ID {token_id} 不存在")
                    return False

                provider = row["provider"]
                token = row["token"]

            # 仅对 zai 提供商验证
            if provider != "zai":
                logger.info(f"⏭️ 跳过非 zai 提供商的 Token 验证: {provider}")
                return True

            # 验证 Token
            from app.utils.token_pool import ZAITokenValidator

            token_type, is_valid, error_msg = await ZAITokenValidator.validate_token(token)

            # 更新 Token 类型
            await self.update_token_type(token_id, token_type)

            if not is_valid:
                logger.warning(f"⚠️ Token 验证失败: id={token_id}, type={token_type}, error={error_msg}")

            return is_valid

        except Exception as e:
            logger.error(f"❌ 验证 Token 失败: {e}")
            return False

    async def validate_all_tokens(self, provider: str = "zai") -> Dict[str, int]:
        """
        批量验证所有 Token

        Args:
            provider: 提供商名称（默认 zai）

        Returns:
            统计结果 {"valid": 数量, "guest": 数量, "invalid": 数量}
        """
        try:
            tokens = await self.get_tokens_by_provider(provider, enabled_only=False)

            if not tokens:
                logger.warning(f"⚠️ 没有需要验证的 {provider} Token")
                return {"valid": 0, "guest": 0, "invalid": 0}

            logger.info(f"🔍 开始批量验证 {len(tokens)} 个 {provider} Token...")

            stats = {"valid": 0, "guest": 0, "invalid": 0}

            for token_record in tokens:
                token_id = token_record["id"]
                is_valid = await self.validate_and_update_token(token_id)

                # 重新查询更新后的类型
                async with self.get_connection() as conn:
                    cursor = await conn.execute("""
                        SELECT token_type FROM tokens WHERE id = ?
                    """, (token_id,))
                    row = await cursor.fetchone()
                    token_type = row["token_type"] if row else "unknown"

                if token_type == "user":
                    stats["valid"] += 1
                elif token_type == "guest":
                    stats["guest"] += 1
                else:
                    stats["invalid"] += 1

            logger.info(f"✅ 批量验证完成: 有效 {stats['valid']}, 匿名 {stats['guest']}, 无效 {stats['invalid']}")
            return stats

        except Exception as e:
            logger.error(f"❌ 批量验证失败: {e}")
            return {"valid": 0, "guest": 0, "invalid": 0}


# 全局单例
_token_dao: Optional[TokenDAO] = None


def get_token_dao() -> TokenDAO:
    """获取全局 TokenDAO 实例"""
    global _token_dao
    if _token_dao is None:
        _token_dao = TokenDAO()
    return _token_dao


async def init_token_database():
    """初始化 Token 数据库"""
    dao = get_token_dao()
    await dao.init_database()
