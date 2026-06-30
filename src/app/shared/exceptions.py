"""Base exception hierarchy for the Clean Architecture layers.

Layer mapping:
  DomainError      — invariant violations (business rules broken in the domain)
  ApplicationError — use case failures (invalid state transition, missing prereq)
  InfrastructureError — external service failures (DB down, network timeout)

HTTP handlers in main.py map these to RFC 7807 Problem Details responses.
"""


class OctopusBaseError(Exception):
    """Root of all custom exceptions in this service."""


# ── Domain layer ──────────────────────────────────────────────────────────────


class DomainError(OctopusBaseError):
    """A domain invariant or business rule was violated."""


# ── Application layer ─────────────────────────────────────────────────────────


class ApplicationError(OctopusBaseError):
    """A use case failed — not a domain invariant, not an infra error."""


class NotFoundError(ApplicationError):
    """The requested resource does not exist."""


class ConflictError(ApplicationError):
    """The operation would violate a uniqueness or state constraint."""


class AuthenticationError(ApplicationError):
    """Identity could not be verified."""


class AuthorizationError(ApplicationError):
    """Identity verified but the caller has insufficient permissions."""


class ValidationError(ApplicationError):
    """Input data failed application-level validation."""


# ── Infrastructure layer ──────────────────────────────────────────────────────


class InfrastructureError(OctopusBaseError):
    """An external dependency (DB, cache, external API) failed."""
