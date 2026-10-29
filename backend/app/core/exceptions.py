"""跨层可解释失败；展示格式由 presentation 层统一决定。"""


class ApiError(Exception):
    """携带安全机器码、用户文案和 HTTP 状态，不包含底层异常详情。"""

    def __init__(self, code: str, message: str, status: int) -> None:
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)
