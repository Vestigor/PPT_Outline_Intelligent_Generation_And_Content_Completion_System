from __future__ import annotations

from app.common.exception.code import Status, StatusCode

class AuthException(Exception):
    """认证异常基类"""
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

    @classmethod
    def exc(cls, status: Status) -> AuthException:
        return cls(status.code, status.message)

    


class BusinessException(Exception):
    """业务异常基类"""
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

    @classmethod
    def exc(cls, status: Status) -> BusinessException:
        return cls(status.code, status.message)