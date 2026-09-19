"""Day-1 correctness fixes: stable vector ids, provider key isolation, model id."""
from __future__ import annotations

import subprocess
import sys

from app.config import settings
from app.llm import registry


# --- stable Qdrant point ids ------------------------------------------------

def test_point_id_is_stable_within_a_process():
    from app.knowledge.store import QdrantStore

    assert QdrantStore._point_id("doc:1") == QdrantStore._point_id("doc:1")


def test_point_id_differs_per_key():
    from app.knowledge.store import QdrantStore

    assert QdrantStore._point_id("doc:1") != QdrantStore._point_id("doc:2")


def test_point_id_fits_qdrant_range():
    from app.knowledge.store import QdrantStore

    pid = QdrantStore._point_id("some-document-key")
    assert 0 <= pid < 2**63


def test_point_id_is_stable_across_processes():
    """Python's hash() is randomised per process, so the previous
    abs(hash(id)) produced a different id on every restart: upsert inserted a
    duplicate instead of updating. This is the regression that matters and it
    can only be caught with a second interpreter."""
    code = (
        "import sys; sys.path.insert(0, '.');"
        "from app.knowledge.store import QdrantStore;"
        "print(QdrantStore._point_id('stable-key'))"
    )
    runs = {
        subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, cwd="."
        ).stdout.strip()
        for _ in range(2)
    }
    assert len(runs) == 1, f"point id changed across processes: {runs}"
    assert runs != {""}, "subprocess produced no output"


# --- provider key isolation -------------------------------------------------

def test_openai_key_setting_exists():
    """Embeddings previously passed settings.anthropic_api_key to the OpenAI
    client, transmitting an sk-ant-... secret to api.openai.com."""
    assert hasattr(settings, "openai_api_key")


def test_embeddings_pass_the_openai_key_not_the_anthropic_one():
    """Checks executable code, ignoring comments — the fix is described in a
    comment that necessarily names the old setting."""
    from pathlib import Path

    code = "\n".join(
        line for line in
        Path("app/knowledge/embeddings.py").read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    )
    assert "settings.anthropic_api_key" not in code
    assert "settings.openai_api_key" in code


# --- model id ---------------------------------------------------------------

def test_default_anthropic_model_is_current():
    """claude-opus-4-8 is not a valid model id; a request with no JALEBI_MODEL
    failed at call time rather than startup."""
    assert "4-8" not in registry.PROVIDERS["anthropic"].default_model
    assert "4-8" not in settings.anthropic_model


def test_config_and_registry_agree_on_the_default_model():
    assert settings.anthropic_model == registry.PROVIDERS["anthropic"].default_model
