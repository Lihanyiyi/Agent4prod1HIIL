# 智能体服务 API

基于 LangGraph 的智能体服务，支持多用户多会话管理。

## 项目结构

```
Agent4prod1HIIL/
├── main.py                 # FastAPI应用主入口
├── requirements.txt        # 项目依赖
├── README.md              # 项目说明文档
├── config/                # 配置模块
│   ├── __init__.py
│   ├── settings.py        # 系统配置
│   └── logging.py         # 日志配置
├── models/                # 数据模型
│   ├── __init__.py
│   └── schemas.py         # Pydantic数据模型
├── services/              # 业务逻辑服务
│   ├── __init__.py
│   ├── Redis_service.py   # Redis会话管理
│   ├── agent_service.py   # 智能体业务逻辑
│   └── api_routes.py      # API路由处理
└── utils/                 # 工具模块
    ├── __init__.py
    ├── config.py          # 配置工具
    ├── llms.py            # LLM工具
    └── tools.py           # 智能体工具
```

## 功能特性

- **多用户多会话管理**: 支持多个用户同时使用，每个用户可以有多个会话
- **智能体中断恢复**: 支持智能体执行中断后的恢复操作
- **长期记忆存储**: 支持用户长期记忆的存储和读取
- **会话状态管理**: 完整的会话状态跟踪和管理
- **RESTful API**: 提供完整的 REST API 接口
- **异步处理**: 基于 FastAPI 的异步处理架构

## 安装依赖

```bash
pip install -r requirements.txt
```

## 环境配置

创建 `.env` 文件并配置以下环境变量：

```env
# 数据库配置
DB_URI=postgresql://user:password@localhost:5432/dbname

# LLM API配置
QWEN_API_KEY=your_qwen_api_key
```

## 启动服务

```bash
python main.py
```

服务将在 `http://localhost:8000` 启动，API 文档可在 `http://localhost:8000/docs` 查看。

## API 接口

### 1. 调用智能体

- **POST** `/agent/invoke`
- 调用智能体处理用户请求

### 2. 恢复智能体执行

- **POST** `/agent/resume`
- 处理智能体中断后的恢复

### 3. 获取会话状态

- **GET** `/agent/status/{user_id}/{session_id}`
- 获取指定会话的状态信息

### 4. 获取用户活跃会话

- **GET** `/agent/active/sessionid/{user_id}`
- 获取用户最近活跃的会话 ID

### 5. 获取用户所有会话

- **GET** `/agent/sessionids/{user_id}`
- 获取用户的所有会话 ID 列表

### 6. 获取系统信息

- **GET** `/system/info`
- 获取系统当前状态信息

### 7. 删除会话

- **DELETE** `/agent/session/{user_id}/{session_id}`
- 删除指定的会话

### 8. 写入长期记忆

- **POST** `/agent/write/longterm`
- 将信息写入用户的长期记忆

### 9. 健康检查

- **GET** `/health`
- 检查服务健康状态

## 重构说明

本项目从原始的 `01_backendServer.py` 单文件重构为模块化架构：

### 重构内容

1. **数据模型分离** (`models/schemas.py`)

   - 将所有 Pydantic 数据模型集中管理
   - 添加了详细的中文注释
   - 支持多用户多会话的数据结构

2. **Redis 服务优化** (`services/Redis_service.py`)

   - 重写为支持多用户多会话的版本
   - 添加了会话清理和状态管理功能
   - 改进了数据存储结构

3. **业务逻辑分离** (`services/agent_service.py`)

   - 将智能体相关业务逻辑独立
   - 包含智能体创建、执行、恢复等核心功能
   - 添加了资源管理和清理功能

4. **API 路由分离** (`services/api_routes.py`)

   - 将所有 API 路由处理逻辑独立
   - 统一的错误处理和日志记录
   - 清晰的接口文档

5. **工具模块** (`utils/`)

   - 配置管理工具
   - LLM 集成工具
   - 智能体工具集合

6. **配置管理** (`config/`)
   - 统一的配置管理
   - 日志配置
   - 环境变量支持

### 重构优势

- **模块化**: 代码结构清晰，便于维护和扩展
- **可读性**: 添加了详细的中文注释
- **可扩展性**: 模块化设计便于添加新功能
- **可测试性**: 各模块独立，便于单元测试
- **可部署性**: 支持环境变量配置，便于不同环境部署
