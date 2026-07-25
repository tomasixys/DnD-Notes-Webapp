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
