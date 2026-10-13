"""认证模块自定义异常：路由层据此映射为 404。"""


class UserNotFoundError(Exception):
    """用户不存在。"""
