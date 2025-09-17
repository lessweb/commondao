class NotFoundError(ValueError):
    pass


class NotTableError(ValueError):
    pass


class MissingParamError(ValueError):
    pass


class TooManyResultError(ValueError):
    pass


class EmptyPrimaryKeyError(ValueError):
    pass
