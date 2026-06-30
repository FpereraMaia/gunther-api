"""Single import point for all SQLAlchemy models.

Import this module wherever Base.metadata must know about all tables:
  - alembic/env.py (autogenerate migrations)
  - tests/conftest.py (create_all for testcontainer)

When adding a new domain, append its model import here:
  from app.infrastructure.database.my_domain.model import MyDomainModel  # noqa: F401
"""
