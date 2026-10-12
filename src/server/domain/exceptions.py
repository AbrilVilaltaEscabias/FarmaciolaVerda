"""Business errors raised by the service layer."""


class NotFoundError(Exception):
    """The requested entity does not exist."""


class AlreadyExistsError(Exception):
    """The entity (or relation) would violate a uniqueness rule."""