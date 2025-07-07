import redis.asyncio as redis
from typing import Dict, Optional, List
import json
from pydantic import BaseModel
import uuid
from datetime import timedelta
from backend.config.logging import logger
from backend.models.schemas import AgentResponse

# 实现redis相关方法 支持多用户多会话
class RedisSessionManager:
    # 初始化 RedisSessionManager 实例
    # 配置 Redis 连接参数和默认会话超时时间
    def __init__(self, redis_host: str, redis_port: int, redis_db: int, session_timeout: int):
        # 创建 Redis 客户端连接
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=True
        )
        # 设置默认会话过期时间（秒）
        self.session_timeout = session_timeout

    # 关闭 Redis 连接
    async def close(self):
        # 异步关闭 Redis 客户端连接
        await self.redis_client.close()

    # 创建指定用户的新会话
    # 存储结构：session:{user_id}:{session_id} = {
    #   "session_id": session_id,
    #   "status": "idle|running|interrupted|completed|error",
    #   "last_response": AgentResponse,
    #   "last_query": str,
    #   "last_updated": timestamp
    # }
    async def create_session(self, user_id: str, session_id: Optional[str] = None, status: str = "active",
                            last_query: Optional[str] = None, last_response: Optional['AgentResponse'] = None,
                            last_updated: Optional[float] = None, ttl: Optional[int] = None) -> str:
        # 如果未提供 session_id，生成新的 UUID
        if session_id is None:
            session_id = str(uuid.uuid4())
        # 如果未提供最后更新时间，设置为 0 秒
        if last_updated is None:
            last_updated = str(timedelta(seconds=0))
        # 使用提供的 TTL 或默认的 session_timeout
        effective_ttl = ttl if ttl is not None else self.session_timeout

        # 构造会话数据结构
        session_data = {
            "session_id": session_id,
            "status": status,
            "last_response": last_response.model_dump() if isinstance(last_response, BaseModel) else last_response,
            "last_query": last_query,
            "last_updated": last_updated
        }

        # 将会话数据存储到 Redis，使用 JSON 序列化，并设置过期时间
        await self.redis_client.set(
            f"session:{user_id}:{session_id}",
            json.dumps(session_data, default=lambda o: o.__dict__ if not hasattr(o, 'model_dump') else o.model_dump()),
            ex=effective_ttl
        )
        # 将 session_id 添加到用户的会话列表中
        await self.redis_client.sadd(f"user_sessions:{user_id}", session_id)
        # 返回新创建的 session_id
        return session_id

    # 更新指定用户的特定会话数据
    async def update_session(self, user_id: str, session_id: str, status: Optional[str] = None,
                            last_query: Optional[str] = None, last_response: Optional['AgentResponse'] = None,
                            last_updated: Optional[float] = None, ttl: Optional[int] = None) -> bool:
        # 检查会话是否存在
        if await self.redis_client.exists(f"session:{user_id}:{session_id}"):
            # 获取当前会话数据
            current_data = await self.get_session(user_id, session_id)
            if not current_data:
                return False
            # 更新提供的字段
            if status is not None:
                current_data["status"] = status
            if last_response is not None:
                if isinstance(last_response, BaseModel):
                    current_data["last_response"] = last_response.model_dump()
                else:
                    current_data["last_response"] = last_response
            if last_query is not None:
                current_data["last_query"] = last_query
            if last_updated is not None:
                current_data["last_updated"] = last_updated
            # 使用提供的 TTL 或默认的 session_timeout
            effective_ttl = ttl if ttl is not None else self.session_timeout
            # 将更新后的数据重新存储到 Redis，并设置新的过期时间
            await self.redis_client.set(
                f"session:{user_id}:{session_id}",
                json.dumps(current_data,
                           default=lambda o: o.__dict__ if not hasattr(o, 'model_dump') else o.model_dump()),
                ex=effective_ttl
            )
            # 更新成功返回 True
            return True
        # 会话不存在返回 False
        return False

    # 获取指定用户当前会话ID的状态数据
    async def get_session(self, user_id: str, session_id: str) -> Optional[dict]:
        # 从 Redis 获取会话数据
        session_data = await self.redis_client.get(f"session:{user_id}:{session_id}")
        # 如果会话不存在，返回 None
        if not session_data:
            return None
        # 解析 JSON 数据
        session = json.loads(session_data)
        # 处理 last_response 字段，尝试转换为 AgentResponse 对象
        if session and "last_response" in session:
            if session["last_response"] is not None:
                try:
                    session["last_response"] = AgentResponse(**session["last_response"])
                except Exception as e:
                    # 记录转换失败的错误日志
                    logger.error(f"转换 last_response 失败: {e}")
                    session["last_response"] = None
        # 返回会话数据
        return session

    # 获取指定用户下的当前激活的会话ID
    async def get_user_active_session_id(self, user_id: str) -> str | None:
        # 在查询前清理指定用户的无效会话
        await self.cleanup_user_sessions(user_id)
        # 获取用户的所有会话ID
        session_ids = await self.redis_client.smembers(f"user_sessions:{user_id}")
        # 如果没有会话，返回 None
        if not session_ids:
            return None
        # 遍历所有会话ID，找到最近更新的会话
        latest_session_id = None
        latest_time = 0
        for session_id in session_ids:
            session_data = await self.get_session(user_id, session_id)
            if session_data and "last_updated" in session_data:
                try:
                    # 尝试将 last_updated 转换为浮点数进行比较
                    last_updated = float(session_data["last_updated"])
                    if last_updated > latest_time:
                        latest_time = last_updated
                        latest_session_id = session_id
                except (ValueError, TypeError):
                    # 如果转换失败，跳过这个会话
                    continue
        # 返回最近更新的会话ID
        return latest_session_id

    # 获取指定用户的所有会话ID
    async def get_all_session_ids(self, user_id: str) -> List[str]:
        # 在查询前清理指定用户的无效会话，确保返回的 session_id 都是有效的
        await self.cleanup_user_sessions(user_id)
        # 获取用户的所有会话ID
        session_ids = await self.redis_client.smembers(f"user_sessions:{user_id}")
        # 返回会话ID列表
        return list(session_ids)

    # 获取所有用户的所有会话ID
    async def get_all_users_session_ids(self) -> Dict[str, List[str]]:
        # 清理所有用户的无效会话
        await self.cleanup_all_sessions()
        # 初始化结果字典
        all_sessions = {}
        # 遍历所有 user_sessions:* 键
        async for key in self.redis_client.scan_iter("user_sessions:*"):
            # 提取用户ID
            user_id = key.split(":", 1)[1]
            # 获取该用户的所有会话ID
            session_ids = await self.redis_client.smembers(key)
            # 将会话ID列表添加到结果字典中
            all_sessions[user_id] = list(session_ids)
        # 返回所有用户的会话ID字典
        return all_sessions

    # 获取指定用户的所有会话数据
    async def get_all_user_sessions(self, user_id: str) -> List[dict]:
        # 初始化会话列表
        sessions = []
        # 获取用户的所有会话ID
        session_ids = await self.get_all_session_ids(user_id)
        # 遍历所有会话ID，获取会话数据
        for session_id in session_ids:
            session_data = await self.get_session(user_id, session_id)
            if session_data:
                sessions.append(session_data)
        # 返回会话数据列表
        return sessions

    # 检查用户ID是否存在
    async def user_id_exists(self, user_id: str) -> bool:
        # 在查询前清理指定用户的无效会话
        await self.cleanup_user_sessions(user_id)
        # 检查用户是否有有效的会话
        session_count = await self.redis_client.scard(f"user_sessions:{user_id}")
        return session_count > 0

    # 检查会话ID是否存在
    async def session_id_exists(self, user_id: str, session_id: str) -> bool:
        # 在查询前清理指定用户的无效会话
        await self.cleanup_user_sessions(user_id)
        # 检查会话是否存在
        return await self.redis_client.sismember(f"user_sessions:{user_id}", session_id)

    # Get session count
    async def get_session_count(self) -> int:
        # 清理所有用户的无效会话
        await self.cleanup_all_sessions()
        # 初始化计数器
        total_count = 0
        # 遍历所有 user_sessions:* 键，计算总会话数
        async for key in self.redis_client.scan_iter("user_sessions:*"):
            count = await self.redis_client.scard(key)
            total_count += count
        # 返回总会话数
        return total_count

    # 清理指定用户的无效会话
    async def cleanup_user_sessions(self, user_id: str) -> None:
        # 获取用户会话集合中的所有 session_id
        session_ids = await self.redis_client.smembers(f"user_sessions:{user_id}")
        # 遍历所有会话ID，检查会话是否仍然存在
        for session_id in session_ids:
            # 检查会话数据是否存在
            if not await self.redis_client.exists(f"session:{user_id}:{session_id}"):
                # 如果会话数据不存在，从用户会话集合中移除该 session_id
                await self.redis_client.srem(f"user_sessions:{user_id}", session_id)

    # 清理所有用户的无效会话
    async def cleanup_all_sessions(self) -> None:
        # 遍历所有 user_sessions:* 键
        async for key in self.redis_client.scan_iter("user_sessions:*"):
            # 提取用户ID
            user_id = key.split(":", 1)[1]
            # 清理该用户的无效会话
            await self.cleanup_user_sessions(user_id)

    # 删除指定用户的特定会话
    async def delete_session(self, user_id: str, session_id: str) -> bool:
        # 从用户会话列表中移除 session_id
        removed = await self.redis_client.srem(f"user_sessions:{user_id}", session_id)
        # 删除会话数据
        deleted = await self.redis_client.delete(f"session:{user_id}:{session_id}")
        # 返回是否成功删除（只要有一个操作成功就认为删除成功）
        return removed > 0 or deleted > 0
