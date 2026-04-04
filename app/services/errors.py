class ServiceError(Exception):
    def __init__(
        self,
        message: str,
        code: str,
        status: int,
        details: dict | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status
        self.details = details


class ValidationError(ServiceError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message=message, code="VALIDATION_ERROR", status=400, details=details)


class ConflictError(ServiceError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message=message, code="CONFLICT", status=409, details=details)


class NotFoundError(ServiceError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message=message, code="NOT_FOUND", status=404, details=details)


class InternalError(ServiceError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message=message, code="INTERNAL_ERROR", status=500, details=details)
