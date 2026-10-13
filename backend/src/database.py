"""全局数据库连接：SQLite 存储应用业务数据（文档系统等）。"""

import sqlite3

from src.config import settings


def get_connection() -> sqlite3.Connection:
    """新建一个 SQLite 连接（按操作创建、用完即关，避免跨线程共享连接）。

    返回的连接已开启外键约束，查询结果以 sqlite3.Row 形式返回，可按列名取值。
    """
    settings.app_db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(settings.app_db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con