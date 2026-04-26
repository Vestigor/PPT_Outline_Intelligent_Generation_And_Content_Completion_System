from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class Status:
    code: int
    message: str

class StatusCode(Enum):
    """
    统一业务状态码。

    格式：(code, message)
    分段规则：
        2xx  — HTTP 语义复用
        2xxx — 用户模块
        3xxx — 会话模块
        4xxx — 知识库 / 文档模块
        5xxx — 报告模块
        6xxx — LLM 模型模块（提供商 / 模型 / 用户配置）
        7xxx — 搜索服务模块（web 搜索 / 检索 / 用户配置）
        8xxx — RAG 模块（Embedding 配置）
    """

    # ------------------------------------------------------------------ #
    # 通用
    # ------------------------------------------------------------------ #
    SUCCESS        = Status(200, "成功")
    BAD_REQUEST    = Status(400, "请求参数错误")
    UNAUTHORIZED   = Status(401, "未授权")
    FORBIDDEN      = Status(403, "禁止访问")
    NOT_FOUND      = Status(404, "资源不存在")
    INTERNAL_ERROR = Status(500, "服务器内部错误")

    # ------------------------------------------------------------------ #
    # 用户模块 2xxx
    # ------------------------------------------------------------------ #
    USER_NOT_FOUND       = Status(2001, "用户不存在")
    DUPLICATE_USERNAME   = Status(2002, "用户名已存在")
    BAD_CREDENTIALS      = Status(2003, "用户名或密码错误")
    USER_NOT_ACTIVE      = Status(2004, "用户被禁用")
    INVALID_OLD_PASSWORD = Status(2005, "旧密码错误")
    SAME_PASSWORD        = Status(2006, "新密码不能与旧密码相同")
    DONT_HAVE_PERMISSION = Status(2007, "权限不足")
    INVALID_JWT          = Status(2008, "无效的令牌")
    INVALID_JWT_TYPE     = Status(2009, "令牌类型错误")
    JWT_EXPIRED          = Status(2010, "令牌已过期")
    JWT_BLACKLISTED      = Status(2011, "令牌已被加入黑名单")

    # ------------------------------------------------------------------ #
    # 会话模块 3xxx
    # ------------------------------------------------------------------ #
    SESSION_NOT_FOUND        = Status(3001, "会话不存在")
    GET_SESSION_LIST_FAILED  = Status(3002, "获取会话列表失败")
    GET_SESSION_FAILED       = Status(3003, "获取会话失败")
    SEND_MESSAGE_FAILED      = Status(3004, "发送消息失败")
    DELETE_SESSION_FAILED    = Status(3005, "删除会话失败")
    INVALID_STAGE_TRANSITION = Status(3006, "无效的阶段转换")

    # ------------------------------------------------------------------ #
    # 知识库 / 文档模块 4xxx
    # ------------------------------------------------------------------ #
    DOCUMENT_NOT_FOUND              = Status(4001, "文档不存在")
    GET_DOCUMENT_LIST_FAILED        = Status(4002, "获取文档列表失败")
    GET_DOCUMENT_FAILED             = Status(4003, "获取文档失败")
    UPLOAD_DOCUMENT_FAILED          = Status(4004, "上传文档失败")
    DOCUMENT_SIZE_EXCEEDED          = Status(4005, "文件大小超过限制")
    DELETE_DOCUMENT_FAILED          = Status(4006, "删除文档失败")
    PARSE_FAILED                    = Status(4007, "解析文档失败")
    VECTORIZE_FAILED                = Status(4008, "向量化文档失败")
    QUERY_FAILED                    = Status(4009, "向量检索失败")
    REMOVE_KNOWLEDGE_REF_FAILED     = Status(4010, "会话知识库关联失败")

    # ------------------------------------------------------------------ #
    # 报告模块 5xxx
    # ------------------------------------------------------------------ #
    REPORT_NOT_FOUND      = Status(5001, "报告不存在")
    REPORT_PARSE_FAILED   = Status(5002, "解析报告失败")
    REPORT_SIZE_EXCEEDED  = Status(5003, "文件大小超过限制")

    # ------------------------------------------------------------------ #
    # LLM 模型模块 6xxx
    # 细分：61xx 提供商，62xx 模型，63xx 用户 LLM 配置，64xx 调用错误
    # ------------------------------------------------------------------ #

    # 提供商（管理员操作）
    LLM_PROVIDER_NOT_FOUND     = Status(6101, "LLM 服务提供商不存在")
    LLM_PROVIDER_DUPLICATE     = Status(6102, "LLM 服务提供商已存在")
    LLM_PROVIDER_DELETE_FAILED = Status(6103, "删除 LLM 服务提供商失败")
    LLM_PROVIDER_DISABLED      = Status(6104, "LLM 服务提供商已停用")

    # 模型（管理员操作）
    LLM_MODEL_NOT_FOUND                  = Status(6201, "LLM 模型不存在")
    LLM_MODEL_DUPLICATE                  = Status(6202, "该提供商下模型已存在")
    LLM_MODEL_DELETE_FAILED              = Status(6203, "删除 LLM 模型失败")
    LLM_MODEL_DISABLED                   = Status(6204, "LLM 模型已停用")
    LLM_MODEL_ENABLE_BLOCKED_BY_PROVIDER = Status(6205, "服务商已停用，请先启用服务商后再启用模型")

    # 用户 LLM 配置
    USER_LLM_CONFIG_NOT_FOUND       = Status(6301, "用户 LLM 配置不存在")
    USER_LLM_CONFIG_DUPLICATE       = Status(6302, "该模型已配置，请勿重复添加")
    USER_LLM_CONFIG_NO_DEFAULT      = Status(6303, "用户尚未设置默认 LLM 配置")
    USER_LLM_CONFIG_API_KEY_MISSING = Status(6304, "LLM API Key 未填写")
    USER_LLM_CONFIG_NOT_ACTIVE      = Status(6305, "该 LLM 配置已停用，不可修改（可删除）")

    # LLM 调用错误
    LLM_API_KEY_INVALID     = Status(6401, "LLM API Key 无效")
    LLM_BASE_URL_INVALID    = Status(6402, "LLM 接口地址错误")
    LLM_GENERATION_FAILED   = Status(6403, "LLM 生成失败")
    LLM_STREAMING_FAILED    = Status(6404, "LLM 流式输出失败")
    LLM_TIMEOUT             = Status(6405, "LLM 请求超时")
    LLM_QUOTA_EXCEEDED      = Status(6406, "LLM 配额已用尽")

    # ------------------------------------------------------------------ #
    # 搜索服务模块 7xxx
    # 细分：71xx 提供商，72xx 用户搜索配置，73xx 调用错误
    # ------------------------------------------------------------------ #

    # 提供商（管理员操作）
    SEARCH_PROVIDER_NOT_FOUND     = Status(7101, "搜索服务提供商不存在")
    SEARCH_PROVIDER_DUPLICATE     = Status(7102, "搜索服务提供商已存在")
    SEARCH_PROVIDER_DELETE_FAILED = Status(7103, "删除搜索服务提供商失败")
    SEARCH_PROVIDER_DISABLED      = Status(7104, "搜索服务提供商已停用")

    # 用户搜索配置
    USER_SEARCH_CONFIG_NOT_FOUND       = Status(7201, "用户搜索配置不存在")
    USER_SEARCH_CONFIG_DUPLICATE       = Status(7202, "该搜索服务已配置，请勿重复添加")
    USER_SEARCH_CONFIG_NO_DEFAULT      = Status(7203, "用户尚未设置默认搜索配置")
    USER_SEARCH_CONFIG_API_KEY_MISSING = Status(7204, "搜索服务 API Key 未填写")
    USER_SEARCH_CONFIG_NOT_ACTIVE      = Status(7205, "该搜索配置已停用，不可修改（可删除）")

    # 搜索调用错误
    WEB_SEARCH_FAILED      = Status(7301, "网络搜索失败")
    RETRIEVAL_FAILED       = Status(7302, "检索服务调用失败")
    SEARCH_API_KEY_INVALID = Status(7303, "搜索服务 API Key 无效")
    SEARCH_TIMEOUT         = Status(7304, "搜索服务请求超时")

    # ------------------------------------------------------------------ #
    # RAG / Embedding 模块 8xxx
    # ------------------------------------------------------------------ #
    USER_RAG_CONFIG_NOT_FOUND     = Status(8001, "用户 RAG 配置不存在（请先填写阿里云 API Key）")
    USER_RAG_CONFIG_ALREADY_EXIST = Status(8002, "用户 RAG 配置已存在")
    RAG_API_KEY_INVALID           = Status(8003, "RAG（阿里云 DashScope）API Key 无效")
    RAG_EMBEDDING_FAILED          = Status(8004, "文本向量化（Embedding）失败")
    RAG_EMBEDDING_TIMEOUT         = Status(8005, "向量化请求超时")

    # ------------------------------------------------------------------ #
    # 大纲 / 幻灯片模块 3xxx（补充）
    # ------------------------------------------------------------------ #
    OUTLINE_NOT_FOUND             = Status(3007, "大纲不存在")
    OUTLINE_ALREADY_CONFIRMED     = Status(3008, "大纲已确认，不可重复确认")
    SLIDE_NOT_FOUND               = Status(3009, "幻灯片内容不存在")
    SLIDE_ALREADY_CONFIRMED       = Status(3010, "幻灯片内容已确认")
    EXPORT_FAILED                 = Status(3011, "PPT 导出失败")
    STAGE_MISMATCH                = Status(3012, "当前会话阶段不支持此操作")

    # ------------------------------------------------------------------ #
    # 任务模块 9xxx
    # ------------------------------------------------------------------ #
    TASK_NOT_FOUND                = Status(9001, "任务不存在")
    TASK_NOT_CANCELLABLE          = Status(9002, "任务已完成或已取消，无法再次取消")
    TASK_NOT_RETRYABLE            = Status(9003, "只有失败的任务可以重试")
    TASK_ACCESS_DENIED            = Status(9004, "无权访问此任务")
