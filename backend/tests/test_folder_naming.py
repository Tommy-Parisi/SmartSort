# tests/test_folder_namer.py
import re
import json
import os
from dataclasses import dataclass
from typing import Dict, List

import pytest

from backend.agents.folder_naming_agent import FolderNamingAgent
from backend.agents.folder_naming_agent import _sanitize_label

# ---- Minimal stand-in for your core.models.ClusteredFile ----
@dataclass
class FakeClusteredFile:
    filename: str = ""
    title: str = ""
    raw_text: str = ""
    path: str = ""


def _build_cluster(files: List[FakeClusteredFile]) -> Dict[int, List[FakeClusteredFile]]:
    # single cluster id 0
    return {0: files}


@pytest.fixture(autouse=True)
def isolate_cache(tmp_path, monkeypatch):
    """
    Redirect the module-level cache file to a temp location so tests
    don't interfere with real runs.
    """
    temp_cache = tmp_path / "folder_name_cache.json"
    monkeypatch.setenv("OPENAI_API_KEY", "")  # ensure no accidental API calls
    # monkeypatch the module-global CACHE_PATH constant
    monkeypatch.setattr("backend.agents.folder_naming_agent.CACHE_PATH", str(temp_cache), raising=False)
    # also ensure a clean file exists
    temp_cache.write_text(json.dumps({}))
    yield
    # test teardown handled by tmp_path cleanup


def words(s: str) -> int:
    return len(s.split())


def has_unsafe_chars(s: str) -> bool:
    return bool(re.search(r'[:<>"/\\|?*\n\r\t]', s))


def test_basic_business_docs_label():
    """
    Should produce a concise, business-y label leveraging filename/title tokens.
    """
    files = [
        FakeClusteredFile(
            filename="Q3_revenue_forecast.xlsx",
            title="Q3 Revenue Projections",
            raw_text="This spreadsheet estimates revenue by segment and region. Updated assumptions..."
        ),
        FakeClusteredFile(
            filename="regional_sales_summary.csv",
            title="Regional Sales",
            raw_text="North America sees growth; EMEA stable; APAC mixed. Quarterly forecast included."
        ),
        FakeClusteredFile(
            filename="board_packet_finance.pdf",
            title="Finance Packet",
            raw_text="Executive summary: revenue forecast, opex trend, margin guidance."
        ),
    ]
    agent = FolderNamingAgent(max_examples=5, use_llm_fallback=False)
    labels = agent.name_clusters(_build_cluster(files))
    label = labels[0]

    assert 1 <= words(label) <= 4
    assert len(label) <= 60
    assert not has_unsafe_chars(label)
    # Soft expectation: it should look like a finance/forecast label
    assert any(kw in label.lower() for kw in ["revenue", "sales", "forecast", "finance"])


def test_policy_docs_filename_weighting():
    """
    Metadata should be weighted, so 'privacy policy' outranks generic 'document' text.
    """
    files = [
        FakeClusteredFile(
            filename="privacy_policy_acme_final.pdf",
            title="Privacy Policy",
            raw_text="Document covers data collection, consent, retention, user rights, DSR."
        ),
        FakeClusteredFile(
            filename="policy_update_change_log.txt",
            title="Policy Update",
            raw_text="Changelog for privacy policy updates aligned with GDPR/CCPA."
        ),
        FakeClusteredFile(
            filename="terms_and_privacy_notes.md",
            title="",
            raw_text="Notes and references for policy maintenance."
        ),
    ]
    agent = FolderNamingAgent(max_examples=5, use_llm_fallback=False)
    label = agent.name_clusters(_build_cluster(files))[0]

    assert 1 <= words(label) <= 4
    assert not has_unsafe_chars(label)
    assert any(kw in label.lower() for kw in ["privacy", "policy"])


def test_tech_docs_trigram_preference():
    """
    Prefer more specific n-grams when available (e.g., 'api integration guide').
    """
    files = [
        FakeClusteredFile(
            filename="api_integration_guide.md",
            title="API Integration Guide",
            raw_text="How to authenticate, rate limits, endpoints, pagination."
        ),
        FakeClusteredFile(
            filename="sdk_quickstart.md",
            title="SDK Quickstart",
            raw_text="Install the SDK, configure environment variables, make your first request."
        ),
        FakeClusteredFile(
            filename="webhook_reference.md",
            title="Webhook Reference",
            raw_text="Events, retries, signatures, delivery semantics."
        ),
    ]
    agent = FolderNamingAgent(max_examples=5, use_llm_fallback=False)
    label = agent.name_clusters(_build_cluster(files))[0]

    assert 1 <= words(label) <= 4
    assert not has_unsafe_chars(label)
    # Should lean toward something like "API Integration" / "Developer Docs" etc.
    assert any(kw in label.lower() for kw in ["api", "integration", "developer", "webhook", "sdk"])


def test_profanity_and_unsafe_char_filtering():
    """
    Ensure the label sanitization removes unsafe characters and profanity if they sneak in.
    """
    # We can't force profanity via heuristics easily; directly test _sanitize_label.
    dirty = 'fin*ance / shiT | forecast <> " : ?'
    clean = _sanitize_label(dirty)
    assert not has_unsafe_chars(clean)
    assert "shit" not in clean.lower()
    assert 1 <= words(clean) <= 4


def test_noise_cluster_is_named_noise():
    cluster_map = {-1: [FakeClusteredFile(filename="foo.txt", raw_text="bar")]}
    agent = FolderNamingAgent(max_examples=3, use_llm_fallback=False)
    labels = agent.name_clusters(cluster_map)
    assert labels[-1] == "Noise"


def test_generic_docs_dont_produce_junky_label():
    """
    If examples are too generic, we should still get a reasonable, compact label (not empty).
    """
    files = [
        FakeClusteredFile(
            filename="document1.txt",
            title="Meeting Notes",
            raw_text="Meeting notes, attendees, action items, next steps."
        ),
        FakeClusteredFile(
            filename="document2.txt",
            title="Notes",
            raw_text="General discussion and follow-ups."
        ),
        FakeClusteredFile(
            filename="document3.txt",
            title="Notes",
            raw_text="Updated meeting notes and to-dos."
        ),
    ]
    agent = FolderNamingAgent(max_examples=5, use_llm_fallback=False)
    label = agent.name_clusters(_build_cluster(files))[0]
    # Shouldn’t be empty; should obey constraints
    assert isinstance(label, str) and len(label) > 0
    assert 1 <= words(label) <= 4
    assert len(label) <= 60
