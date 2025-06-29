# react_agents/config/settings.py
from pydantic import Field

import os
from typing import List, Dict, Any


class Settings:
    # API configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Log configuration
    LOG_FILE: str = "logfile/agent_service.log"
    if not os.path.exists(os.path.dirname(LOG_FILE)):
        os.makedirs(os.path.dirname(LOG_FILE))
    MAX_BYTES: int = 5 * 1024 * 1024  # 5MB
    BACKUP_COUNT: int = 3

    # Redis configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    SESSION_TIMEOUT: int = 3600  # 1小时

    # PostgreSQL configuration
    DB_URI: str = os.environ.get("DB_URI", "postgresql://user:password@localhost:5432/dbname")
    MIN_SIZE: int = 5
    MAX_SIZE: int = 20

    # LLM configuration
    LLM_TYPE: str = "qwen"
    OPENAI_API_KEY: str = os.environ.get("QWEN_API_KEY", "")

    # 系统配置
    SYSTEM_MESSAGE: str = "你会使用工具来帮助用户。如果工具使用被拒绝，请提示用户。"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def __post_init__(self):
        """初始化后处理，确保日志目录存在"""
        if not os.path.exists(os.path.dirname(self.LOG_FILE)):
            os.makedirs(os.path.dirname(self.LOG_FILE))


settings = Settings()