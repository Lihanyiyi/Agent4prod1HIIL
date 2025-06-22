# react_agents/models/schemas.py
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from ..config.settings import settings
import uuid
import time

class AgentRequest(BaseModel):
    user_id: str
    query: str
    system_message: Optional[str] = settings.SYSTEM_MESSAGE

class AgentResponse(BaseModel):
    session_id: str
    status: str  # interrupted, completed, error
    timestamp: float = Field(default_factory=lambda: time.time())
    message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    interrupt_data: Optional[Dict[str, Any]] = None

class InterruptResponse(BaseModel):
    user_id: str
    session_id: str
    response_type: str  # accept, edit, response, reject
    args: Optional[Dict[str, Any]] = None

class SystemInfoResponse(BaseModel):
    sessions_count: int
    active_users: List[str]

class SessionStatusResponse(BaseModel):
    user_id: str
    session_id: Optional[str] = None
    status: str  # not_found, idle, running, interrupted, completed, error
    message: Optional[str] = None
    last_query: Optional[str] = None
    last_updated: Optional[float] = None
    last_response: Optional[AgentResponse] = None