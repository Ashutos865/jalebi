"""Backend configuration, sourced from environment variables (12-factor).

Only non-secret defaults live here. Secrets (API keys, OAuth secrets, JWT signing
key) are read from the environment and never committed. Everything degrades to a
runnable local default: SQLite, in-memory vector store, mock AI provider.
See `.env.example`.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List

# Auto-load a local .env if python-dotenv is installed (dev convenience).
try:  # pragma: no cover
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass


def _csv(name: str, default: str) -> List[str]:
    return [x.strip() for x in os.getenv(name, default).split(",") if x.strip()]


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    app_name: str = "Jalebi"
    environment: str = os.getenv("JALEBI_ENV", "development")

    # --- AI provider selection -------------------------------------------------
    # Active provider: mock | anthropic | openai | gemini | ollama | openrouter |
    #                  groq | together | deepseek | mistral | xai
    # JALEBI_EVALUATOR is the legacy name (mock|claude); mapped for back-compat.
    provider: str = os.getenv(
        "JALEBI_PROVIDER",
        {"claude": "anthropic"}.get(
            os.getenv("JALEBI_EVALUATOR", "mock"), os.getenv("JALEBI_EVALUATOR", "mock")
        ),
    )
    # Providers a request is allowed to select (defaults to any that are configured).
    allowed_providers: List[str] = field(
        default_factory=lambda: _csv("JALEBI_ALLOWED_PROVIDERS", "")
    )
    # Thinking/output effort for providers that support it.
    effort: str = os.getenv("JALEBI_EFFORT", "medium")

    # Model overrides (empty → provider default). Keys/base-urls read in the registry.
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("JALEBI_MODEL", "claude-opus-4-8")

    # --- Auth (P3) -------------------------------------------------------------
    jwt_secret: str = os.getenv("JALEBI_JWT_SECRET", "dev-insecure-change-me")
    jwt_algorithm: str = "HS256"
    jwt_ttl_minutes: int = int(os.getenv("JALEBI_JWT_TTL_MIN", "720"))
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    google_redirect_uri: str = os.getenv(
        "GOOGLE_REDIRECT_URI", "http://127.0.0.1:8000/api/auth/google/callback"
    )
    # Exact origin the OAuth success page may postMessage the token to. Empty →
    # derived from google_redirect_uri. Never "*": that hands the bearer token to
    # any site that opened the popup.
    oauth_post_message_origin: str = os.getenv("JALEBI_OAUTH_POSTMESSAGE_ORIGIN", "")
    # Comma-separated emails granted admin on first login (founders).
    admin_emails: List[str] = field(
        default_factory=lambda: _csv("JALEBI_ADMIN_EMAILS", "")
    )
    # Email/secret login (no OAuth). In production, gate it with a shared secret and
    # an allow-list so it isn't an open admin backdoor.
    allow_dev_login: bool = _bool("JALEBI_ALLOW_DEV_LOGIN", True)
    # Shared secret required to log in (empty = no secret required — dev only).
    signup_secret: str = os.getenv("JALEBI_SIGNUP_SECRET", "")
    # Allow-list: exact emails and/or email domains. Empty lists = allow any email
    # (dev). Set at least one in production.
    allowed_emails: List[str] = field(
        default_factory=lambda: _csv("JALEBI_ALLOWED_EMAILS", "")
    )
    allowed_domains: List[str] = field(
        default_factory=lambda: _csv("JALEBI_ALLOWED_DOMAINS", "")
    )
    # Require a valid token on /evaluate etc. Off by default so P1/P2 keep working;
    # turn on in production.
    require_auth: bool = _bool("JALEBI_REQUIRE_AUTH", False)

    # Security middleware
    security_headers: bool = _bool("JALEBI_SECURITY_HEADERS", True)
    request_logging: bool = _bool("JALEBI_REQUEST_LOG", True)

    # --- Database (P3) ---------------------------------------------------------
    # SQLAlchemy async URL. Default = local SQLite file.
    database_url: str = os.getenv(
        "JALEBI_DATABASE_URL", "sqlite+aiosqlite:///./jalebi.db"
    )
    # Auto-create tables on startup (convenient for dev). Set false in production and
    # manage the schema with Alembic (`alembic upgrade head`).
    auto_create_tables: bool = _bool("JALEBI_AUTO_CREATE", True)

    # --- Knowledge base / RAG (P4) --------------------------------------------
    rag_enabled: bool = _bool("JALEBI_RAG_ENABLED", True)
    rag_top_k: int = int(os.getenv("JALEBI_RAG_TOP_K", "4"))
    qdrant_url: str = os.getenv("QDRANT_URL", "")          # empty → in-memory store
    qdrant_api_key: str = os.getenv("QDRANT_API_KEY", "")
    embedding_backend: str = os.getenv("JALEBI_EMBEDDING", "hash")  # hash | openai

    # --- Pipeline (P5) ---------------------------------------------------------
    # single-call LLM vs multi-agent (one reviewer call per dimension group).
    pipeline_mode: str = os.getenv("JALEBI_PIPELINE", "single")  # single | multi

    # --- Grammar engine (inline, real-time checking) ---------------------------
    # LanguageTool server URL. Empty → dependency-free heuristic checker.
    languagetool_url: str = os.getenv("JALEBI_LANGUAGETOOL_URL", "")

    # --- Integrations (P6) -----------------------------------------------------
    slack_webhook_url: str = os.getenv("JALEBI_SLACK_WEBHOOK", "")
    teams_webhook_url: str = os.getenv("JALEBI_TEAMS_WEBHOOK", "")
    notify_on_ready: bool = _bool("JALEBI_NOTIFY_ON_READY", False)

    # --- Monitoring (P6) -------------------------------------------------------
    sentry_dsn: str = os.getenv("SENTRY_DSN", "")

    # --- HTTP ------------------------------------------------------------------
    cors_origins: List[str] = field(
        default_factory=lambda: _csv("JALEBI_CORS_ORIGINS", "*")
    )
    max_document_chars: int = int(os.getenv("JALEBI_MAX_CHARS", "60000"))
    rate_limit_per_min: int = int(os.getenv("JALEBI_RATE_LIMIT", "60"))


settings = Settings()


# --- Production safety gate ----------------------------------------------------

# The default signing key is published in this repository, so any deployment still
# using it can have admin tokens forged against it.
INSECURE_JWT_SECRET = "dev-insecure-change-me"
MIN_JWT_SECRET_BYTES = 32


def unsafe_production_settings(s: "Settings" = None) -> List[str]:
    """Return the reasons `s` is unsafe to run with JALEBI_ENV=production.

    Empty list == safe. Kept pure and separate from startup so it can be unit
    tested and reused by a pre-deploy check.
    """
    s = s or settings
    problems: List[str] = []

    if s.jwt_secret == INSECURE_JWT_SECRET:
        problems.append(
            "JALEBI_JWT_SECRET is still the public default value — tokens can be forged. "
            "Set it to a random string (e.g. `python -c \"import secrets;"
            "print(secrets.token_urlsafe(48))\"`)."
        )
    elif len(s.jwt_secret) < MIN_JWT_SECRET_BYTES:
        problems.append(
            f"JALEBI_JWT_SECRET is {len(s.jwt_secret)} characters; "
            f"use at least {MIN_JWT_SECRET_BYTES}."
        )

    # Dev-login is passwordless. Without a shared secret AND an allow-list it is an
    # open door to account creation — and to admin, via JALEBI_ADMIN_EMAILS.
    if s.allow_dev_login:
        if not s.signup_secret:
            problems.append(
                "JALEBI_ALLOW_DEV_LOGIN=true without JALEBI_SIGNUP_SECRET is an open "
                "registration endpoint. Set the secret, or JALEBI_ALLOW_DEV_LOGIN=false."
            )
        if not s.allowed_emails and not s.allowed_domains:
            problems.append(
                "JALEBI_ALLOW_DEV_LOGIN=true with no allow-list accepts any email "
                "address. Set JALEBI_ALLOWED_EMAILS or JALEBI_ALLOWED_DOMAINS."
            )

    if "*" in s.cors_origins:
        problems.append(
            "JALEBI_CORS_ORIGINS=* lets any website call this API with a stolen "
            "bearer token. List the exact origins instead."
        )

    return problems


def enforce_production_safety(s: "Settings" = None) -> None:
    """Refuse to start an unsafe production deployment. No-op outside production."""
    s = s or settings
    if s.environment != "production":
        return
    problems = unsafe_production_settings(s)
    if problems:
        raise RuntimeError(
            "Refusing to start: unsafe production configuration.\n  - "
            + "\n  - ".join(problems)
            + "\n\nSee apps/backend/.env.production.example. To run these settings "
            "anyway (never on a public host), set JALEBI_ENV=development."
        )
