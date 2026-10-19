class AppError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


def provider_error(status: int, code: str = "") -> AppError:
    if code.startswith("subscription_sharing_usage_") or status == 429:
        return AppError("usage_limit", "Your ChatGPT usage limit was reached. Open Manage usage.", 429)
    if status in (401, 403):
        return AppError("sign_in_required", "Reconnect ChatGPT and check plan-usage permission.", 401)
    return AppError("provider_error", "ChatGPT could not complete the request. Your inputs are preserved.", 502)
