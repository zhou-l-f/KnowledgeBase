"""认证与权限模块常量：角色定义与权限分组。"""

# 角色定义（权限由高到低）
ROLE_ADMIN = "admin"
ROLE_EDITOR = "editor"
ROLE_READONLY = "readonly"

# 全部合法角色
ALL_ROLES = (ROLE_ADMIN, ROLE_EDITOR, ROLE_READONLY)

# 可写内容的角色：新增/修改/删除知识库、文档、问答、媒体
CONTENT_WRITE_ROLES = (ROLE_ADMIN, ROLE_EDITOR)
