"""会话模块自定义异常：路由层据此映射为 404。"""


class ConversationNotFoundError(Exception):
    """会话不存在，或不属于当前登录用户（越权访问一律视为不存在）。"""