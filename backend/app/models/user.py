"""SQLAlchemy async ORM model for users."""

import uuid

from sqlalchemy import Boolean, Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID

from app.db.postgres import Base


class User(Base):
    """Platform user account.

    Attributes:
        id: Primary key (UUID).
        username: Unique username handle.
        email: Unique e-mail address.
        hashed_password: bcrypt-hashed password.
        full_name: Optional display name.
        roles: List of role strings (viewer | analyst | admin).
        clearance_level: Data clearance (public | internal | confidential | secret).
        tenant_id: Multi-tenancy isolation key.
        is_active: Whether the account is enabled.
        created_at: Row creation timestamp.
        updated_at: Last modification timestamp.
    """

    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        nullable=False,
    )
    username = Column(String(128), nullable=False, unique=True, index=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    hashed_password = Column(String(256), nullable=False)
    full_name = Column(String(255), nullable=True)
    roles = Column(ARRAY(String), nullable=False, default=list)
    clearance_level = Column(String(64), nullable=False, default="internal")
    tenant_id = Column(String(128), nullable=False, default="default", index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"
