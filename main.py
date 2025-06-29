from fastapi import FastAPI
from contextlib import asynccontextmanager
import uvicorn
from config.logging import logger
from config.settings import settings
from services.api_routes import (
    invoke_agent_handler, resume_agent_handler, get_agent_status_handler,
    get_agent_active_sessionid_handler, get_agent_sessionids_handler,
    get_system_info_handler, delete_agent_session_handler, write_long_term_handler,
    cleanup_redis_manager
)
from services.agent_service import cleanup_resources
from models.schemas import (
    AgentRequest, AgentResponse, InterruptResponse, LongMemRequest,
    SessionStatusResponse, ActiveSessionInfoResponse, SessionInfoResponse,
    SystemInfoResponse
)

# 应用生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI应用生命周期管理
    
    Args:
        app: FastAPI应用实例
    """
    # 启动时的初始化
    logger.info("应用启动中...")
    logger.info(f"服务器配置: HOST={settings.HOST}, PORT={settings.PORT}")
    logger.info(f"Redis配置: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
    logger.info(f"数据库配置: {settings.DB_URI}")
    logger.info("应用启动完成")
    
    yield
    
    # 关闭时的清理
    logger.info("应用关闭中...")
    try:
        # 清理Redis管理器
        await cleanup_redis_manager()
        # 清理其他资源
        await cleanup_resources()
        logger.info("应用关闭完成")
    except Exception as e:
        logger.error(f"应用关闭时出错: {e}")

# 创建FastAPI应用实例
app = FastAPI(
    title="智能体服务API",
    description="基于LangGraph的智能体服务，支持多用户多会话管理",
    version="1.0.0",
    lifespan=lifespan
)

# API路由定义

@app.post("/agent/invoke", response_model=AgentResponse)
async def invoke_agent(request: AgentRequest):
    """
    调用智能体
    
    - **user_id**: 用户唯一标识
    - **session_id**: 会话唯一标识
    - **query**: 用户的问题
    - **system_message**: 系统提示词（可选）
    
    返回智能体执行结果，包括状态（interrupted/completed/error）和相应数据
    """
    return await invoke_agent_handler(request)

@app.post("/agent/resume", response_model=AgentResponse)
async def resume_agent(response: InterruptResponse):
    """
    恢复智能体执行
    
    - **user_id**: 用户唯一标识
    - **session_id**: 会话唯一标识
    - **response_type**: 响应类型（accept/edit/response/reject）
    - **args**: 额外参数（可选）
    
    用于处理智能体执行中断后的恢复操作
    """
    return await resume_agent_handler(response)

@app.get("/agent/status/{user_id}/{session_id}", response_model=SessionStatusResponse)
async def get_agent_status(user_id: str, session_id: str):
    """
    获取智能体状态
    
    - **user_id**: 用户唯一标识
    - **session_id**: 会话唯一标识
    
    返回指定会话的详细状态信息
    """
    return await get_agent_status_handler(user_id, session_id)

@app.get("/agent/active/sessionid/{user_id}", response_model=ActiveSessionInfoResponse)
async def get_agent_active_sessionid(user_id: str):
    """
    获取用户活跃会话ID
    
    - **user_id**: 用户唯一标识
    
    返回用户最近活跃的会话ID
    """
    return await get_agent_active_sessionid_handler(user_id)

@app.get("/agent/sessionids/{user_id}", response_model=SessionInfoResponse)
async def get_agent_sessionids(user_id: str):
    """
    获取用户所有会话ID
    
    - **user_id**: 用户唯一标识
    
    返回用户的所有会话ID列表
    """
    return await get_agent_sessionids_handler(user_id)

@app.get("/system/info", response_model=SystemInfoResponse)
async def get_system_info():
    """
    获取系统信息
    
    返回系统当前状态，包括会话总数和活跃用户信息
    """
    return await get_system_info_handler()

@app.delete("/agent/session/{user_id}/{session_id}")
async def delete_agent_session(user_id: str, session_id: str):
    """
    删除指定会话
    
    - **user_id**: 用户唯一标识
    - **session_id**: 会话唯一标识
    
    删除指定的会话及其相关数据
    """
    return await delete_agent_session_handler(user_id, session_id)

@app.post("/agent/write/longterm")
async def write_long_term(request: LongMemRequest):
    """
    写入长期记忆
    
    - **user_id**: 用户唯一标识
    - **memory_info**: 要写入的记忆信息
    
    将信息写入用户的长期记忆中
    """
    return await write_long_term_handler(request)

# 健康检查接口
@app.get("/health")
async def health_check():
    """
    健康检查接口
    
    返回服务健康状态
    """
    return {"status": "healthy", "message": "智能体服务运行正常"}

# 根路径接口
@app.get("/")
async def root():
    """
    根路径接口
    
    返回服务基本信息
    """
    return {
        "message": "智能体服务API",
        "version": "1.0.0",
        "author": "Lihan",
        "docs": "/docs"
    }

# 主函数
if __name__ == "__main__":
    # 启动服务器
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,  # 开发模式下启用热重载
        log_level="info"
    ) 