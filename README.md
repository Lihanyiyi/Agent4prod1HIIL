# Agent4prod1HIIL: Multi-Session AI Agent Service

## Overview

**Agent4prod1HIIL** is a robust, production-ready backend system for managing multi-user, multi-session AI agents with advanced features such as tool-use, long-term memory, and Human-in-the-Loop (HIL) interruption and review. It is built on FastAPI, Celery, Redis, PostgreSQL, and LangGraph, and is designed for extensibility, reliability, and real-world deployment.

---

## Key Features & Value

### 🤖 Multi-User, Multi-Session AI Agent

- Each user can have multiple independent sessions, each with multiple tasks.
- Every session and task is tracked and managed in real time.

### 🔄 Asynchronous Task Processing

- All agent invocations are handled asynchronously via Celery, ensuring scalability and responsiveness.
- Users receive a task ID immediately and can poll for status/results.

### 🛠️ Tool Use & Human-in-the-Loop (HIL)

- Agents can call external tools as part of their reasoning.
- If a tool call requires human approval, the session is **interrupted** and can be resumed after user confirmation.

### 💾 Long-Term Memory

- Users can write and store long-term memory, which is used to enhance agent context and performance.

### 🗂️ Session & Task Management

- Full CRUD for sessions and tasks: create, list, delete, and status query.
- System-wide and per-user session statistics.

### 🩺 Health & Observability

- Built-in health check endpoint.
- System info endpoint for monitoring active users and sessions.

---

## API Endpoints & Usage

### Agent Task Lifecycle

- **POST `/agent/invoke`**  
  Start a new agent task (asynchronous).  
  **Returns:** `{user_id, session_id, task_id}`

- **POST `/agent/resume`**  
  Resume an interrupted agent task after human review.  
  **Returns:** `{user_id, session_id, task_id}`

- **GET `/agent/status/{user_id}/{session_id}/{task_id}`**  
  Get the current status and result of a specific task.  
  **Returns:** Task status, last query, last response, etc.

### Session & Task Management

- **GET `/agent/sessionids/{user_id}`**  
  List all session IDs for a user.

- **GET `/agent/tasks/{user_id}/{session_id}`**  
  List all task IDs and statuses for a session.

- **DELETE `/agent/session/{user_id}/{session_id}`**  
  Delete a session and all its tasks.

- **DELETE `/agent/task/{user_id}/{session_id}/{task_id}`**  
  Delete a specific task from a session.

- **GET `/agent/active/sessionid/{user_id}`**  
  Get the most recently updated session for a user.

### Long-Term Memory

- **POST `/agent/write/longterm`**  
  Write long-term memory for a user.  
  **Body:** `{user_id, memory_info}`

### System & Health

- **GET `/system/info`**  
  Get system-wide statistics: total sessions, active users, etc.

- **GET `/health`**  
  Health check endpoint.

---

## Project Value

- **Scalable**: Asynchronous, distributed task processing with Celery.
- **Extensible**: Easily add new tools, agent logic, or memory strategies.
- **Production-Ready**: Robust error handling, session cleanup, and resource management.
- **Human-in-the-Loop**: Real-world safety and compliance for tool use and critical actions.
- **Observability**: System info and health endpoints for monitoring and operations.

---

## Quick Start

### Prerequisites

- Python 3.8+
- Redis
- PostgreSQL

### Installation & Run

1. **Install backend dependencies:**

   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Start Redis and PostgreSQL** (use Docker or system services).

3. **Start Celery worker:**

   ```bash
   celery -A backend.services.agent_service worker --loglevel=info
   ```

4. **Start FastAPI server:**

   ```bash
   python main.py
   ```

---

## License

MIT License

---

**Agent4prod1HIIL** empowers you to build safe, scalable, and intelligent agent applications for real-world, multi-user environments.
