"""Backend configuration, sourced from environment variables (12-factor).

Only non-secret defaults live here. Secrets (API keys, OAuth secrets, JWT signing
key) are read from the environment and never committed. Everything degrades to a
runnable local default: SQLite, in-memory vector store, mock AI provider.
See `.env.example`.
"""
from __future__ import annotations

import logging
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

    # Per-request timeout and retry budget for every LLM provider. Without these
    # the SDK defaults apply (~600s), and because the evaluator retries once on a
    # parse failure a stalled provider could hold a request — and its DB session
    # — for roughly twenty minutes.
    llm_timeout_seconds: float = float(os.getenv("JALEBI_LLM_TIMEOUT", "60"))
    llm_max_retries: int = int(os.getenv("JALEBI_LLM_RETRIES", "2"))
    # Ceiling on a whole evaluation, including retries and any concurrent fan-out.
    llm_total_timeout_seconds: float = float(
        os.getenv("JALEBI_LLM_TOTAL_TIMEOUT", "180")
    )

    # Model overrides (empty → provider default). Keys/base-urls read in the registry.
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    # Used by the OpenAI embeddings backend (JALEBI_EMBEDDING=openai). Provider
    # keys for evaluation are resolved in app/llm/registry.py from their own env
    # vars; this one is here because embeddings read settings directly.
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    anthropic_model: str = os.getenv("JALEBI_MODEL", "claude-sonnet-5")

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
    # Worker count, for the multi-worker checks below. Gunicorn and Uvicorn both
    # honour WEB_CONCURRENCY; a process manager that does not set it looks like a
    # single worker, which is the safe assumption.
    web_concurrency: int = int(os.getenv("WEB_CONCURRENCY", "1"))
    qdrant_api_key: str = os.getenv("QDRANT_API_KEY", "")
    embedding_backend: str = os.getenv("JALEBI_EMBEDDING", "hash")  # hash | openai

    # --- Pipeline (P5) ---------------------------------------------------------
    # single-call LLM vs multi-agent (one reviewer call per dimension group).
    # NOTE: JALEBI_PIPELINE (single|multi) was removed. The multi-agent
    # evaluator it selected was unreachable dead code and has been deleted;
    # every provider runs through HybridEvaluator. Setting it now does nothing,
    # so it is no longer read rather than being silently ignored.

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
    # Reverse proxies whose X-Forwarded-For we trust, as IPs or CIDR blocks.
    # Empty (the default) means the server is directly exposed and the header is
    # ignored — it is attacker-controlled otherwise. Set this when running behind
    # Caddy/nginx/a load balancer, e.g. "127.0.0.1,10.0.0.0/8".
    trusted_proxies: List[str] = field(
        default_factory=lambda: _csv("JALEBI_TRUSTED_PROXIES", "")
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

    # The in-memory vector store is a process global, so each worker builds and
    # holds its own index. With several workers the same document retrieves
    # different supporting passages depending on which worker answers — and the
    # startup reindex runs once per worker. Silent, and impossible to diagnose
    # from the outside.
    problems.extend(misconfiguration_warnings(s))

    return problems


def misconfiguration_warnings(s: "Settings" = None) -> List[str]:
    """Problems worth saying out loud in any environment.

    Separate from the production gate: these produce wrong behaviour rather than
    an insecure one, so they are worth a warning even in development, where the
    gate is deliberately inert.
    """
    s = s or settings
    warnings: List[str] = []

    # getattr with defaults: this runs against Settings in production and against
    # lightweight stand-ins in tests, and a new check should never break a caller
    # that predates the field it reads.
    workers = getattr(s, "web_concurrency", 1)
    rag_on = getattr(s, "rag_enabled", False)
    qdrant = getattr(s, "qdrant_url", "")

    # The in-memory vector store is a process global, so each worker builds and
    # holds its own index: the same document retrieves different supporting
    # passages depending on which worker answers, and the startup reindex runs
    # once per worker. Silent, and impossible to diagnose from outside.
    if rag_on and not qdrant and workers > 1:
        warnings.append(
            f"WEB_CONCURRENCY={workers} with no QDRANT_URL: the vector store is "
            "per-process, so retrieval results will vary between workers. Set "
            "QDRANT_URL, run a single worker, or set JALEBI_RAG_ENABLED=false."
        )
    return warnings


def enforce_production_safety(s: "Settings" = None) -> None:
    """Refuse to start an unsafe production deployment. No-op outside production."""
    s = s or settings
    if s.environment != "production":
        # Still surface anything that would silently misbehave.
        for warning in misconfiguration_warnings(s):
            logging.getLogger("jalebi").warning("Configuration: %s", warning)
        return
    problems = unsafe_production_settings(s)
    if problems:
        raise RuntimeError(
            "Refusing to start: unsafe production configuration.\n  - "
            + "\n  - ".join(problems)
            + "\n\nSee apps/backend/.env.production.example. To run these settings "
            "anyway (never on a public host), set JALEBI_ENV=development."
        )
