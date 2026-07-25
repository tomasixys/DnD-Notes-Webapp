from enum import Enum


class UserStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class SystemRole(str, Enum):
    USER = "user"
    ADMIN = "admin"
    CUSTODIAN = "custodian"


class AccountTokenPurpose(str, Enum):
    ACTIVATION = "activation"
    PASSWORD_RESET = "password_reset"


class SecurityEventType(str, Enum):
    LOGIN_SUCCEEDED = "login_succeeded"
    LOGIN_FAILED = "login_failed"
    LOGIN_SOURCE_THROTTLED = "login_source_throttled"
    USER_INVITED = "user_invited"
    ACCOUNT_ACTIVATED = "account_activated"
    PASSWORD_RESET_REQUESTED = "password_reset_requested"
    PASSWORD_RESET_COMPLETED = "password_reset_completed"
    ACCOUNT_DELETED = "account_deleted"
