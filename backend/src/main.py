from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse

from src.agent import agent_router, warmup
from src.agent.config import agent_settings
from src.auth import auth_init, auth_router
from src.conversation import conversation_init, conversation_router
from src.database import get_connection
from src.document import document_init, document_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[system] 应用启动，模块加载中", flush=True)
    auth_init()  # 认证模块：users 表建表 + .env 初始管理员导入
    document_init()  # 文档模块：建表 + 向量库自检（失败则阻止启动）
    conversation_init()  # 会话模块：会话/消息表建表
    warmup()  # agent 模块：LLM 链预热（失败则阻止启动）
    print("[system] 模块加载完成")
    yield
    print("[system] 应用关闭，释放资源")


app = FastAPI(lifespan=lifespan)


@app.get("/health", tags=["系统"])
def health(response: Response) -> dict:
    """健康检查：数据库连通性与 LLM 配置（部署探针用，无需登录）。"""
    try:
        with get_connection() as con:
            con.execute("select 1")
        database = "ok"
    except Exception:
        database = "unavailable"
    if database != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ok" if database == "ok" else "degraded",
        "database": database,
        "llm_configured": bool(agent_settings.deepseek_api_key),
    }


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """兜底异常处理：未捕获异常统一返回 500，避免向前端泄露堆栈。"""
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误"})


app.include_router(auth_router)
app.include_router(agent_router)
app.include_router(document_router)
app.include_router(conversation_router)