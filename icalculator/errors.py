from OneTicketLogging import elasticsearch_logger

_logger = elasticsearch_logger(__name__)


class BaseError(Exception):
    def __init__(self, message, *args, **kwargs):
        _logger.exception(message)
        super().__init__(message, *args, **kwargs)


class ClientError(BaseError):
    def __init__(self, message, *args, **kwargs):
        super().__init__('Client error: ' + message, *args, **kwargs)


class ServiceError(BaseError):
    def __init__(self, message, *args, **kwargs):
        super().__init__('Service error: ' + message, *args, **kwargs)
