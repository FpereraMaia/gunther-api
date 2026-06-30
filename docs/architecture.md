# Architecture

Gunther API follows Clean Architecture — dependencies point inward,
the domain layer has no external dependencies.

## Layer diagram

```mermaid
graph TD
    subgraph Presentation
        API[FastAPI routers]
        MW[Middleware]
        SCH[Pydantic schemas]
    end

    subgraph Application
        UC[Use cases]
        CMD[Commands / Queries]
        TASKS[Background tasks]
    end

    subgraph Domain
        ENT[Entities]
        VO[Value objects]
        REPO[Repository interfaces]
        SVC[Domain services]
    end

    subgraph Infrastructure
        DB[(SQLAlchemy)]
        CACHE[(Redis)]
        EXT[External clients]
        REPOIMPL[Repository impls]
    end

    API --> UC
    MW --> UC
    UC --> ENT
    UC --> REPO
    UC --> SVC
    REPOIMPL --> DB
    REPOIMPL --> CACHE
    REPOIMPL -->|implements| REPO
    TASKS --> UC
```

## Directory structure

```
src/app/
├── domain/
│   ├── <domain>/
│   │   ├── entities.py       # Dataclasses, no ORM coupling
│   │   ├── value_objects.py
│   │   ├── repository.py     # Abstract base class
│   │   └── services.py       # Pure domain logic
│   └── shared/
├── application/
│   └── <domain>/
│       ├── commands.py       # Mutating use cases
│       ├── queries.py        # Read use cases
│       └── tasks.py          # ARQ background tasks
├── infrastructure/
│   ├── database/
│   │   └── <domain>/
│   │       ├── models.py     # SQLAlchemy ORM models
│   │       └── repository.py # Concrete implementation
│   ├── cache/                # Redis helpers
│   └── security/             # JWT helpers
└── presentation/
    └── api/
        └── v1/
            └── <domain>/
                ├── router.py
                └── schemas.py
```

## Dependency injection

Dependencies are wired in `src/app/presentation/dependencies.py` using FastAPI's
`Depends()`. Database sessions and repository instances are scoped per HTTP request.

## Conventions

- Entities are plain Python dataclasses — no SQLAlchemy in the domain layer
- Use cases receive repository interfaces via constructor injection
- All I/O operations are `async`
- Response schemas (out) and request schemas (in) are separate Pydantic models
