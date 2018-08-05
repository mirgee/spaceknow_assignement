class InitiateException(Exception):
    """Raised when a /initiate endpoint returns response with no pipelineId field."""
    pass


class NotProcessedException(Exception):
    """Raise when the endpoint is not ready with response yet, but is still
    processing. Should be caught by the caller if this is expected."""
    pass


class FieldNotFoundException(Exception):
    """Raise when returned json does not contain an expected field."""
    pass


class FatalException(Exception):
    """Raise in case of irrecoverable exception."""
    pass
