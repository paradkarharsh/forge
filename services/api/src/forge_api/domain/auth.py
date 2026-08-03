from enum import StrEnum


class WorkspaceRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    MAINTAINER = "maintainer"
    DEVELOPER = "developer"
    VIEWER = "viewer"
