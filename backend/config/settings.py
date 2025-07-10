# react_agents/config/settings.py
from pydantic import Field
from pydantic_settings import BaseSettings

import os
from typing import List, Dict, Any


class AppConfig(BaseSettings):
    # 日志持久化存储
    LOG_FILE: str = "logfile/app.log"
    MAX_BYTES: int = 5*1024*1024
    BACKUP_COUNT: int = 3

    # PostgreSQL数据库配置参数
    DB_URI: str = os.getenv("DB_URI", "postgresql://postgres:postgres@localhost:5432/postgres?sslmode=disable")
    MIN_SIZE: int = 5
    MAX_SIZE: int = 10

    # Redis数据库配置参数
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    SESSION_TIMEOUT: int = 300
    TTL: int = 3600

    # Celery配置
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    TASK_TTL: int = 3600

    # LLM配置
    LLM_TYPE: str = "qwen"
    OPENAI_API_KEY: str = os.environ.get("QWEN_API_KEY", "")

    # API服务地址和端口
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # 系统配置
    SYSTEM_MESSAGE: str = "你会使用工具来帮助用户。如果工具使用被拒绝，请提示用户。"

    # 鉴权相关配置（保留原有）
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "your_secret_key_here")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 确保日志目录存在
        if not os.path.exists(os.path.dirname(self.LOG_FILE)):
            os.makedirs(os.path.dirname(self.LOG_FILE))

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

app_config = AppConfig()