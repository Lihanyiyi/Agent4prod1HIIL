import time
from typing import Dict, Any, Optional, List
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres import AsyncPostgresStore
from langchain_core.messages.utils import trim_messages
from psycopg_pool import AsyncConnectionPool
from backend.config.logging import logger
from backend.config import settings
from backend.models.schemas import AgentResponse, AgentRequest, InterruptResponse
from backend.services.Redis_service import RedisSessionManager
from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta

# 全局变量存储智能体实例和数据库连接
agent_instances: Dict[str, Any] = {}
db_pool: Optional[AsyncConnectionPool] = None
redis_manager: Optional[RedisSessionManager] = None

# Password hashing context - using sha256_crypt for better compatibility
pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

SECRET_KEY = "your_secret_key_here"  # Should be set in config
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

# 初始化数据库连接池
async def init_db_pool():
    """初始化PostgreSQL数据库连接池"""
    global db_pool
    if db_pool is None:
        db_pool = AsyncConnectionPool(
            conninfo=settings.DB_URI,
            min_size=settings.MIN_SIZE,
            max_size=settings.MAX_SIZE
        )
    return db_pool

# 初始化Redis管理器
async def init_redis_manager():
    """初始化Redis会话管理器"""
    global redis_manager
    if redis_manager is None:
        redis_manager = RedisSessionManager(
            redis_host=settings.REDIS_HOST,
            redis_port=settings.REDIS_PORT,
            redis_db=settings.REDIS_DB,
            session_timeout=settings.SESSION_TIMEOUT
        )
    return redis_manager

# 解析消息内容
async def parse_messages(messages: List[Any]) -> None:
    """
    解析并打印消息内容，用于调试
    
    Args:
        messages: 消息列表
    """
    for i, message in enumerate(messages):
        if hasattr(message, 'content'):
            logger.debug(f"Message {i}: {message.content}")
        else:
            logger.debug(f"Message {i}: {message}")

# 处理智能体执行结果
async def process_agent_result(
        session_id: str,
        result: Dict[str, Any],
        user_id: Optional[str] = None
) -> AgentResponse:
    """
    处理智能体执行结果，转换为标准响应格式
    
    Args:
        session_id: 会话ID
        result: 智能体执行结果
        user_id: 用户ID（可选）
    
    Returns:
        AgentResponse: 标准化的响应对象
    """
    try:
        # 检查结果类型
        if "interrupt" in result:
            # 处理中断情况
            interrupt_data = result["interrupt"]
            logger.info(f"智能体执行被中断: {interrupt_data}")
            return AgentResponse(
                session_id=session_id,
                status="interrupted",
                interrupt_data=interrupt_data
            )
        elif "error" in result:
            # 处理错误情况
            error_message = result["error"]
            logger.error(f"智能体执行出错: {error_message}")
            return AgentResponse(
                session_id=session_id,
                status="error",
                message=str(error_message)
            )
        else:
            # 处理正常完成情况
            logger.info(f"智能体执行完成: {result}")
            return AgentResponse(
                session_id=session_id,
                status="completed",
                result=result
            )
    except Exception as e:
        # 处理异常情况
        logger.error(f"处理智能体结果时出错: {e}")
        return AgentResponse(
            session_id=session_id,
            status="error",
            message=f"处理结果时出错: {str(e)}"
        )

# 消息裁剪钩子函数
def trimmed_messages_hook(state):
    """
    消息裁剪钩子函数，用于处理消息长度限制
    
    Args:
        state: 当前状态
    
    Returns:
        处理后的状态
    """
    messages = state["messages"]
    if len(messages) > 10:
        # 如果消息数量超过10条，进行裁剪
        trimmed = trim_messages(messages, max_tokens=4000)
        state["messages"] = trimmed
    return state

# 读取长期记忆信息
async def read_long_term_info(user_id: str) -> str:
    """
    从Redis读取用户的长期记忆信息
    
    Args:
        user_id: 用户ID
    
    Returns:
        str: 长期记忆信息
    """
    try:
        redis_manager = await init_redis_manager()
        # 从Redis读取长期记忆
        memory_data = await redis_manager.redis_client.get(f"long_term_memory:{user_id}")
        if memory_data:
            return memory_data
        else:
            return "无长期记忆信息"
    except Exception as e:
        logger.error(f"读取长期记忆失败: {e}")
        return f"读取长期记忆失败: {str(e)}"

# 写入长期记忆信息
async def write_long_term_info(user_id: str, memory_info: str) -> bool:
    """
    将信息写入用户的长期记忆
    
    Args:
        user_id: 用户ID
        memory_info: 要写入的记忆信息
    
    Returns:
        bool: 写入是否成功
    """
    try:
        redis_manager = await init_redis_manager()
        # 将记忆信息写入Redis，设置过期时间为30天
        await redis_manager.redis_client.set(
            f"long_term_memory:{user_id}",
            memory_info,
            ex=30 * 24 * 3600  # 30天
        )
        logger.info(f"成功写入长期记忆: user_id={user_id}")
        return True
    except Exception as e:
        logger.error(f"写入长期记忆失败: {e}")
        return False

# 获取或创建智能体实例
async def get_or_create_agent(session_id: str) -> Any:
    """
    获取或创建智能体实例
    
    Args:
        session_id: 会话ID
    
    Returns:
        Any: 智能体实例
    """
    if session_id not in agent_instances:
        try:
            # 初始化数据库连接池
            db_pool = await init_db_pool()
            
            # 创建PostgreSQL存储
            store = AsyncPostgresStore(
                pool=db_pool,
                table_name=f"checkpoints_{session_id}"
            )
            
            # 创建PostgreSQL保存器
            saver = AsyncPostgresSaver(
                pool=db_pool,
                table_name=f"checkpoints_{session_id}"
            )
            
            # 导入工具和LLM
            from backend.utils.tools import get_tools
            from backend.utils.llms import get_llm
            
            # 获取工具和LLM
            tools = get_tools()
            llm = get_llm()
            
            # 创建React智能体
            agent = create_react_agent(
                llm=llm,
                tools=tools,
                state_modifier=trimmed_messages_hook
            )
            
            # 绑定存储和保存器
            app = agent.bind(
                checkpointer=saver,
                interrupt_before=["action"]
            )
            
            # 存储智能体实例
            agent_instances[session_id] = app
            
            logger.info(f"创建新的智能体实例: session_id={session_id}")
            
        except Exception as e:
            logger.error(f"创建智能体实例失败: {e}")
            raise
    
    return agent_instances[session_id]

# 执行智能体
async def execute_agent(request: AgentRequest) -> AgentResponse:
    """
    执行智能体
    
    Args:
        request: 智能体请求
    
    Returns:
        AgentResponse: 执行结果
    """
    try:
        # 初始化Redis管理器
        redis_manager = await init_redis_manager()
        
        # 获取或创建智能体实例
        agent = await get_or_create_agent(request.session_id)
        
        # 更新会话状态为运行中
        await redis_manager.update_session(
            user_id=request.user_id,
            session_id=request.session_id,
            status="running",
            last_query=request.query,
            last_updated=time.time()
        )
        
        # 读取长期记忆
        long_term_memory = await read_long_term_info(request.user_id)
        
        # 构建系统消息
        system_message = request.system_message or "你会使用工具来帮助用户。如果工具使用被拒绝，请提示用户。"
        if long_term_memory and long_term_memory != "无长期记忆信息":
            system_message += f"\n\n用户的长期记忆信息：{long_term_memory}"
        
        # 执行智能体
        result = await agent.ainvoke({
            "messages": [{
                "role": "system",
                "content": system_message
            }, {
                "role": "user",
                "content": request.query
            }]
        })
        
        # 处理执行结果
        agent_response = await process_agent_result(
            session_id=request.session_id,
            result=result,
            user_id=request.user_id
        )
        
        # 更新会话状态
        status = "idle" if agent_response.status == "completed" else agent_response.status
        await redis_manager.update_session(
            user_id=request.user_id,
            session_id=request.session_id,
            status=status,
            last_response=agent_response,
            last_updated=time.time()
        )
        
        return agent_response
        
    except Exception as e:
        logger.error(f"执行智能体失败: {e}")
        
        # 更新会话状态为错误
        if redis_manager:
            await redis_manager.update_session(
                user_id=request.user_id,
                session_id=request.session_id,
                status="error",
                last_updated=time.time()
            )
        
        return AgentResponse(
            session_id=request.session_id,
            status="error",
            message=f"执行智能体失败: {str(e)}"
        )

# 恢复智能体执行
async def resume_agent(response: InterruptResponse) -> AgentResponse:
    """
    恢复智能体执行
    
    Args:
        response: 中断响应
    
    Returns:
        AgentResponse: 执行结果
    """
    try:
        # 初始化Redis管理器
        redis_manager = await init_redis_manager()
        
        # 获取智能体实例
        agent = await get_or_create_agent(response.session_id)
        
        # 更新会话状态为运行中
        await redis_manager.update_session(
            user_id=response.user_id,
            session_id=response.session_id,
            status="running",
            last_updated=time.time()
        )
        
        # 根据响应类型处理中断
        if response.response_type == "accept":
            # 接受工具调用
            result = await agent.ainvoke({
                "messages": [{
                    "role": "user",
                    "content": "请继续执行"
                }]
            })
        elif response.response_type == "edit":
            # 编辑工具参数
            result = await agent.ainvoke({
                "messages": [{
                    "role": "user",
                    "content": f"请使用修改后的参数继续执行: {response.args}"
                }]
            })
        elif response.response_type == "response":
            # 直接反馈信息
            result = await agent.ainvoke({
                "messages": [{
                    "role": "user",
                    "content": f"用户反馈: {response.args}"
                }]
            })
        elif response.response_type == "reject":
            # 拒绝工具调用
            result = await agent.ainvoke({
                "messages": [{
                    "role": "user",
                    "content": "工具调用被拒绝，请重新考虑解决方案"
                }]
            })
        else:
            raise ValueError(f"不支持的响应类型: {response.response_type}")
        
        # 处理执行结果
        agent_response = await process_agent_result(
            session_id=response.session_id,
            result=result,
            user_id=response.user_id
        )
        
        # 更新会话状态
        status = "idle" if agent_response.status == "completed" else agent_response.status
        await redis_manager.update_session(
            user_id=response.user_id,
            session_id=response.session_id,
            status=status,
            last_response=agent_response,
            last_updated=time.time()
        )
        
        return agent_response
        
    except Exception as e:
        logger.error(f"恢复智能体执行失败: {e}")
        
        # 更新会话状态为错误
        if redis_manager:
            await redis_manager.update_session(
                user_id=response.user_id,
                session_id=response.session_id,
                status="error",
                last_updated=time.time()
            )
        
        return AgentResponse(
            session_id=response.session_id,
            status="error",
            message=f"恢复智能体执行失败: {str(e)}"
        )

# 清理资源
async def cleanup_resources():
    """清理所有资源"""
    global db_pool, redis_manager
    
    # 关闭数据库连接池
    if db_pool:
        await db_pool.close()
        db_pool = None
    
    # 关闭Redis连接
    if redis_manager:
        await redis_manager.close()
        redis_manager = None
    
    # 清空智能体实例
    agent_instances.clear()
    
    logger.info("资源清理完成") 