from fastapi import HTTPException, APIRouter, Depends, Query, Body
from backend.config.logging import logger
from backend.models.schemas import (
    AgentRequest, AgentResponse, InterruptResponse, LongMemRequest,
    SessionStatusResponse, ActiveSessionInfoResponse, SessionInfoResponse,
    SystemInfoResponse, UserRegisterRequest, UserLoginRequest, UserResponse, TokenResponse, User,
    HILReview, HILReviewCreate, HILReviewUpdate, HILReviewResponse
)
from backend.services.agent_service import execute_agent, resume_agent, write_long_term_info, get_password_hash, verify_password, create_access_token, decode_access_token
from backend.services.Redis_service import RedisSessionManager
from backend.config.settings import settings
import time
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from typing import List
from pydantic import BaseModel

# 全局Redis管理器实例
redis_manager: RedisSessionManager = None

DATABASE_URL = settings.DB_URI
engine = create_engine(DATABASE_URL, echo=True, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        if payload is None:
            raise credentials_exception
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

# 初始化Redis管理器
async def get_redis_manager() -> RedisSessionManager:
    """获取Redis管理器实例"""
    global redis_manager
    if redis_manager is None:
        redis_manager = RedisSessionManager(
            redis_host=settings.REDIS_HOST,
            redis_port=settings.REDIS_PORT,
            redis_db=settings.REDIS_DB,
            session_timeout=settings.SESSION_TIMEOUT
        )
    return redis_manager

# 智能体调用接口
async def invoke_agent_handler(request: AgentRequest) -> AgentResponse:
    """
    处理智能体调用请求
    
    Args:
        request: 智能体请求
    
    Returns:
        AgentResponse: 执行结果
    """
    try:
        logger.info(f"收到智能体调用请求: user_id={request.user_id}, session_id={request.session_id}")
        
        # 获取Redis管理器
        redis_manager = await get_redis_manager()
        
        # 检查会话是否存在，如果不存在则创建新会话
        if not await redis_manager.session_id_exists(request.user_id, request.session_id):
            await redis_manager.create_session(
                user_id=request.user_id,
                session_id=request.session_id,
                status="idle",
                last_updated=time.time()
            )
            logger.info(f"创建新会话: user_id={request.user_id}, session_id={request.session_id}")
        
        # 执行智能体
        response = await execute_agent(request)
        
        logger.info(f"智能体调用完成: session_id={request.session_id}, status={response.status}")
        return response
        
    except Exception as e:
        logger.error(f"智能体调用失败: {e}")
        raise HTTPException(status_code=500, detail=f"智能体调用失败: {str(e)}")

# 智能体恢复接口
async def resume_agent_handler(response: InterruptResponse) -> AgentResponse:
    """
    处理智能体恢复请求
    
    Args:
        response: 中断响应
    
    Returns:
        AgentResponse: 执行结果
    """
    try:
        logger.info(f"收到智能体恢复请求: user_id={response.user_id}, session_id={response.session_id}")
        
        # 获取Redis管理器
        redis_manager = await get_redis_manager()
        
        # 检查会话是否存在
        if not await redis_manager.session_id_exists(response.user_id, response.session_id):
            raise HTTPException(status_code=404, detail="会话不存在")
        
        # 恢复智能体执行
        result = await resume_agent(response)
        
        logger.info(f"智能体恢复完成: session_id={response.session_id}, status={result.status}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"智能体恢复失败: {e}")
        raise HTTPException(status_code=500, detail=f"智能体恢复失败: {str(e)}")

# 获取智能体状态接口
async def get_agent_status_handler(user_id: str, session_id: str) -> SessionStatusResponse:
    """
    获取智能体状态
    
    Args:
        user_id: 用户ID
        session_id: 会话ID
    
    Returns:
        SessionStatusResponse: 会话状态
    """
    try:
        logger.info(f"获取智能体状态: user_id={user_id}, session_id={session_id}")
        
        # 获取Redis管理器
        redis_manager = await get_redis_manager()
        
        # 获取会话数据
        session_data = await redis_manager.get_session(user_id, session_id)
        
        if not session_data:
            # 会话不存在
            return SessionStatusResponse(
                user_id=user_id,
                session_id=session_id,
                status="not_found"
            )
        
        # 返回会话状态
        return SessionStatusResponse(
            user_id=user_id,
            session_id=session_id,
            status=session_data.get("status", "unknown"),
            message=session_data.get("message"),
            last_query=session_data.get("last_query"),
            last_updated=session_data.get("last_updated"),
            last_response=session_data.get("last_response")
        )
        
    except Exception as e:
        logger.error(f"获取智能体状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取智能体状态失败: {str(e)}")

# 获取用户活跃会话ID接口
async def get_agent_active_sessionid_handler(user_id: str) -> ActiveSessionInfoResponse:
    """
    获取用户活跃会话ID
    
    Args:
        user_id: 用户ID
    
    Returns:
        ActiveSessionInfoResponse: 活跃会话信息
    """
    try:
        logger.info(f"获取用户活跃会话ID: user_id={user_id}")
        
        # 获取Redis管理器
        redis_manager = await get_redis_manager()
        
        # 获取活跃会话ID
        active_session_id = await redis_manager.get_user_active_session_id(user_id)
        
        if not active_session_id:
            raise HTTPException(status_code=404, detail="用户没有活跃会话")
        
        return ActiveSessionInfoResponse(active_session_id=active_session_id)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取用户活跃会话ID失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取用户活跃会话ID失败: {str(e)}")

# 获取用户所有会话ID接口
async def get_agent_sessionids_handler(user_id: str) -> SessionInfoResponse:
    """
    获取用户所有会话ID
    
    Args:
        user_id: 用户ID
    
    Returns:
        SessionInfoResponse: 会话ID列表
    """
    try:
        logger.info(f"获取用户所有会话ID: user_id={user_id}")
        
        # 获取Redis管理器
        redis_manager = await get_redis_manager()
        
        # 获取所有会话ID
        session_ids = await redis_manager.get_all_session_ids(user_id)
        
        return SessionInfoResponse(session_ids=session_ids)
        
    except Exception as e:
        logger.error(f"获取用户所有会话ID失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取用户所有会话ID失败: {str(e)}")

# 获取系统信息接口
async def get_system_info_handler(current_user: User = Depends(get_current_user)) -> SystemInfoResponse:
    """
    获取系统信息
    
    Returns:
        SystemInfoResponse: 系统信息
    """
    try:
        logger.info("获取系统信息")
        
        # 获取Redis管理器
        redis_manager = await get_redis_manager()
        
        # 获取会话总数
        sessions_count = await redis_manager.get_session_count()
        
        # 获取所有用户的会话信息
        all_users_sessions = await redis_manager.get_all_users_session_ids()
        
        return SystemInfoResponse(
            sessions_count=sessions_count,
            active_users=all_users_sessions
        )
        
    except Exception as e:
        logger.error(f"获取系统信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取系统信息失败: {str(e)}")

# 删除会话接口
async def delete_agent_session_handler(user_id: str, session_id: str) -> dict:
    """
    删除指定会话
    
    Args:
        user_id: 用户ID
        session_id: 会话ID
    
    Returns:
        dict: 删除结果
    """
    try:
        logger.info(f"删除会话: user_id={user_id}, session_id={session_id}")
        
        # 获取Redis管理器
        redis_manager = await get_redis_manager()
        
        # 检查会话是否存在
        if not await redis_manager.session_id_exists(user_id, session_id):
            raise HTTPException(status_code=404, detail="会话不存在")
        
        # 删除会话
        success = await redis_manager.delete_session(user_id, session_id)
        
        if not success:
            raise HTTPException(status_code=500, detail="删除会话失败")
        
        logger.info(f"会话删除成功: user_id={user_id}, session_id={session_id}")
        return {"message": "会话删除成功"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除会话失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除会话失败: {str(e)}")

# 写入长期记忆接口
async def write_long_term_handler(request: LongMemRequest) -> dict:
    """
    写入长期记忆
    
    Args:
        request: 长期记忆请求
    
    Returns:
        dict: 写入结果
    """
    try:
        logger.info(f"写入长期记忆: user_id={request.user_id}")
        
        # 写入长期记忆
        success = await write_long_term_info(request.user_id, request.memory_info)
        
        if not success:
            raise HTTPException(status_code=500, detail="写入长期记忆失败")
        
        logger.info(f"长期记忆写入成功: user_id={request.user_id}")
        return {"message": "长期记忆写入成功"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"写入长期记忆失败: {e}")
        raise HTTPException(status_code=500, detail=f"写入长期记忆失败: {str(e)}")

# 清理Redis管理器
async def cleanup_redis_manager():
    """清理Redis管理器"""
    global redis_manager
    if redis_manager:
        await redis_manager.close()
        redis_manager = None
        logger.info("Redis管理器已清理")

def get_message(msg_en, msg_zh, lang):
    return msg_zh if lang == 'zh' else msg_en

@router.post("/register", response_model=UserResponse)
def register_user(user: UserRegisterRequest, db: Session = Depends(get_db), lang: str = Query('en', description="Language: en or zh")):
    # Check if username or email exists
    if db.query(User).filter((User.username == user.username) | (User.email == user.email)).first():
        raise HTTPException(status_code=400, detail=get_message("Username or email already registered", "用户名或邮箱已被注册", lang))
    hashed_password = get_password_hash(user.password)
    db_user = User(username=user.username, email=user.email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return UserResponse(id=db_user.id, username=db_user.username, email=db_user.email)

@router.post("/login", response_model=TokenResponse)
def login_user(user: UserLoginRequest, db: Session = Depends(get_db), lang: str = Query('en', description="Language: en or zh")):
    db_user = db.query(User).filter(User.username == user.username).first()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail=get_message("Incorrect username or password", "用户名或密码错误", lang))
    access_token = create_access_token({"sub": db_user.username, "user_id": db_user.id})
    return TokenResponse(access_token=access_token)

@router.post("/hil/review", response_model=HILReviewResponse)
def create_hil_review(review: HILReviewCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_review = HILReview(**review.dict())
    db.add(db_review)
    db.commit()
    db.refresh(db_review)
    return db_review

@router.get("/hil/review", response_model=List[HILReviewResponse])
def list_hil_reviews(skip: int = 0, limit: int = 20, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    reviews = db.query(HILReview).order_by(HILReview.created_at.desc()).offset(skip).limit(limit).all()
    return reviews

@router.get("/hil/review/{review_id}", response_model=HILReviewResponse)
def get_hil_review(review_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    review = db.query(HILReview).filter(HILReview.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review

@router.put("/hil/review/{review_id}", response_model=HILReviewResponse)
def update_hil_review(review_id: int, update: HILReviewUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    review = db.query(HILReview).filter(HILReview.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    for key, value in update.dict(exclude_unset=True).items():
        setattr(review, key, value)
    db.commit()
    db.refresh(review)
    return review

class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str

@router.post("/user/change-password")
def change_password(request: PasswordChangeRequest = Body(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not verify_password(request.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Old password is incorrect")
    current_user.hashed_password = get_password_hash(request.new_password)
    db.commit()
    return {"message": "Password updated successfully"} 