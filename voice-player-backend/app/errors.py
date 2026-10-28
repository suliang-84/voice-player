"""业务错误：code 为接口文档 1.3 / 8.1 的业务码，http_status 为传输层状态码。"""

HTTP_STATUS = {
    400: 400, 401: 401, 403: 403, 404: 404, 500: 500, 503: 503,
    40001: 404,  # 音频不存在
    40002: 200,  # 转写尚未完成：业务状态，不是传输层失败
    40003: 415,  # 文件格式不支持
    40004: 413,  # 文件过大
    40005: 429,  # 配额用尽
    40007: 403,  # 权限不足
    50001: 503,  # 服务暂时不可用
    50002: 422,  # 文件处理失败
}


class AppError(Exception):
    def __init__(self, code: int, message: str, data=None, http_status: int | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data
        self.http_status = http_status or HTTP_STATUS.get(code, 500)


def audio_not_found(audio_id: str) -> AppError:
    return AppError(40001, f"音频不存在：{audio_id}")
