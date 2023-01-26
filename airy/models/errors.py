from lightbulb import CheckFailure


class DatabaseStateConflictError(Exception):
    """
    Raised when the database's state conflicts with the operation requested to be carried out.
    """


class AiryError(Exception):
    """
    Base Airy exception class. All errors raised by lightbulb will be a subclass
    of this exception.
    """


class ServiceNotFound(AiryError):
    """Exception raised when an attempt is made to load a service that does not exist."""


class ServiceAlreadyLoaded(AiryError):
    """Exception raised when a service already loaded is attempted to be loaded."""


class ServiceMissingLoad(AiryError):
    """Exception raised when a service is attempted to be loaded but does not contain a load function"""


class ServiceMissingUnload(AiryError):
    """Exception raised when a service is attempted to be unloaded but does not contain an unload function"""


class ServiceNotLoaded(AiryError):
    """Exception raised when a service not already loaded is attempted to be unloaded."""


class ErrorForUser(AiryError):
    pass


class BadArgument(ErrorForUser):
    pass


class RoleHierarchyError(CheckFailure):
    """
    Raised when an action fails due to role hierarchy.
    """


class BotRoleHierarchyError(CheckFailure):
    """
    Raised when an action fails due to the bot's role hierarchy.
    """


class MemberExpectedError(AiryError):
    """
    Raised when a command expected a member and received a user instead.
    """


class UserBlacklistedError(AiryError):
    """
    Raised when a user who is blacklisted from using the application tries to use it.
    """


class DMFailedError(AiryError):
    """
    Raised when DMing a user fails while executing a moderation command.
    """


class TimeConversionError(AiryError):
    """
    Raised when a tag is not found, although most functions just return None.
    """


class TimeInPast(TimeConversionError):
    pass


class TimeInFuture(TimeConversionError):
    pass


class RoleAlreadyExists(AiryError):
    def __init__(self):
        self.message = "This role already exists."


class RoleDoesNotExist(AiryError):
    def __init__(self):
        self.message = "This role does not exists."

class InteractionTimeOutError(Exception):
    """
    Raised when a user interaction times out.
    """