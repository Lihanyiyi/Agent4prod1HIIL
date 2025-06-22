import redis.asyncio as redis
from typing import Dict, Any, Optional, List
import json
from pydantic import BaseModel
import uuid
from datetime import timedelta
from ..config.logging import logger
from ..models.schemas import AgentResponse

class RedisSessionManager:
    # Initialize the asynchronous Redis connection and session configuration
    def __init__(self, redis_host, redis_port, redis_db, session_timeout):
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=True
        )
        self.session_timeout = session_timeout

        # close Redis connection
    async def close(self):
        await self.redis_client.close()

    # Create a new session to match the specified data structure
    # Session storage - Saves the agent instance and state of each user
    # only one session for one user is supported. Multiple sessions for one user are not allowed
    # structure: {user_id: {
    #   "session_id": session_id,   # 会话ID
    #   "status": "idle|running|interrupted|completed|error",
    #   "last_response": AgentResponse,
    #   "last_query": str,
    #   "last_updated": timestamp
    # }}
    async def create_session(self, user_id: str, session_id: Optional[str] = None, status: str = "active",
                                 last_query: Optional[str] = None, last_response: Optional['AgentResponse'] = None,
                                 last_updated: Optional[float] = None) -> str:
        if session_id is None:
            session_id = str(uuid.uuid4())
        if last_updated is None:
            last_updated = str(timedelta(seconds=0))
        session_data = {
            user_id: {
                "session_id": session_id,
                "status": status,
                "last_response": last_response.model_dump() if isinstance(last_response,
                                BaseModel) else last_response,
                "last_query": last_query,
                "last_updated": last_updated
            }
        }
        await self.redis_client.set(
            f"session:{user_id}",
            json.dumps(session_data,
                default=lambda o: o.__dict__ if not hasattr(o, 'model_dump') else o.model_dump()),
                ex=self.session_timeout
            )
        return session_id

    # Obtain Session data
    async def get_session(self, user_id: str) -> Optional[dict]:
        session_data = await self.redis_client.get(f"session:{user_id}")
        if not session_data:
            return None
        session = json.loads(session_data).get(user_id)
        if session and "last_response" in session:
            if session["last_response"] is not None:
                try:
                    session["last_response"] = AgentResponse(**session["last_response"])
                except Exception as e:
                    logger.error(f"Failure for converting last_response: {e}")
                    session["last_response"] = None
        return session

    # Update session data
    async def update_session(self, user_id: str, status: Optional[str] = None, last_query: Optional[str] = None,
                             last_response: Optional['AgentResponse'] = None, last_updated: Optional[float] = None) -> bool:
        if await self.redis_client.exists(f"session:{user_id}"):
            current_data = await self.get_session(user_id)
            if not current_data:
                return False
            # Update provided values
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
            # Maintain the data structure
            session_data = {user_id: current_data}
            # Re-store and refresh the expiration time
            await self.redis_client.set(
                f"session:{user_id}",
                json.dumps(session_data, default=lambda o: o.__dict__ if not hasattr(o, 'model_dump') else o.model_dump()),
                ex=self.session_timeout
            )
            return True
        return False

    # Delete Session
    async def delete_session(self, user_id: str) -> bool:
        return (await self.redis_client.delete(f"session:{user_id}")) > 0

    # Get session count
    async def get_session_count(self) -> int:
        count = 0
        async for _ in self.redis_client.scan_iter("session:*"):
            count += 1
        return count
    # Obtain all user_id
    async def get_all_user_ids(self) -> List[str]:
        user_ids = []
        async for key in self.redis_client.scan_iter("session:*"):
            user_id = key.split(":", 1)[1]
            user_ids.append(user_id)
        return user_ids

    # Check whether user_id in Redis
    async def user_id_exists(self, user_id: str) -> bool:
        return (await self.redis_client.exists(f"session:{user_id}")) > 0
