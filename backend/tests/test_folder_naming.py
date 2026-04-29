# tests/test_folder_namer.py
import re
import json
import os
from dataclasses import dataclass
from typing import Dict, List

import pytest

from backend.agents.folder_naming_agent import FolderNamingAgent
from backend.agents.folder_naming_agent import _sanitize_label
from backend.core.models import ClusteredFile, FileMeta

def _fake_clustered_file(filename: str, raw_text: str = "") -> ClusteredFile:
    meta = FileMeta(
        file_path=f"/tmp/{filename}",
        file_name=filename,
        extension=os.path.splitext(filename)[1],
        detected_type="text",
        size_kb=1.0,
        created_at="2024-01-01T00:00:00",
        modified_at="2024-01-01T00:00:00",
    )
    return ClusteredFile(file_meta=meta, embedding=[0.1, 0.2], raw_text=raw_text, cluster_id=0)


def _build_cluster(files: List[ClusteredFile]) -> Dict[int, List[ClusteredFile]]:
    # single cluster id 0
    return {0: files}


@pytest.fixture(autouse=True)
def isolate_cache(tmp_path, monkeypatch):
    """
    Redirect the module-level cache file to a temp location so tests
    don't interfere with real runs.
    """
    temp_cache = tmp_path / "folder_name_cache.json"
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
        _fake_clustered_file("Q3_revenue_forecast.xlsx", "This spreadsheet estimates revenue by segment and region. Updated assumptions..."),
        _fake_clustered_file("regional_sales_summary.csv", "North America sees growth; EMEA stable; APAC mixed. Quarterly forecast included."),
        _fake_clustered_file("board_packet_finance.pdf", "Executive summary: revenue forecast, opex trend, margin guidance."),
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
        _fake_clustered_file("privacy_policy_acme_final.pdf", "Document covers data collection, consent, retention, user rights, DSR."),
        _fake_clustered_file("policy_update_change_log.txt", "Changelog for privacy policy updates aligned with GDPR/CCPA."),
        _fake_clustered_file("terms_and_privacy_notes.md", "Notes and references for policy maintenance."),
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
        _fake_clustered_file("api_integration_guide.md", "How to authenticate, rate limits, endpoints, pagination."),
        _fake_clustered_file("sdk_quickstart.md", "Install the SDK, configure environment variables, make your first request."),
        _fake_clustered_file("webhook_reference.md", "Events, retries, signatures, delivery semantics."),
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
    cluster_map = {-1: [_fake_clustered_file("foo.txt", "bar")]}
    agent = FolderNamingAgent(max_examples=3, use_llm_fallback=False)
    labels = agent.name_clusters(cluster_map)
    assert labels[-1] == "Unsorted"


def test_generic_docs_dont_produce_junky_label():
    """
    If examples are too generic, we should still get a reasonable, compact label (not empty).
    """
    files = [
        _fake_clustered_file("document1.txt", "Meeting notes, attendees, action items, next steps."),
        _fake_clustered_file("document2.txt", "General discussion and follow-ups."),
        _fake_clustered_file("document3.txt", "Updated meeting notes and to-dos."),
    ]
    agent = FolderNamingAgent(max_examples=5, use_llm_fallback=False)
    label = agent.name_clusters(_build_cluster(files))[0]
    # Shouldn’t be empty; should obey constraints
    assert isinstance(label, str) and len(label) > 0
    assert 1 <= words(label) <= 4
    assert len(label) <= 60


def test_filename_proper_noun_noise_is_removed():
    files = [
        _fake_clustered_file("Thomas_resume.pdf", "resume software engineering python experience"),
        _fake_clustered_file("health_plan.pdf", "plan coverage eligibility deductible benefits"),
    ]
    agent = FolderNamingAgent(max_examples=5, use_llm_fallback=False)
    label = agent.name_clusters(_build_cluster(files))[0]
    assert "thomas" not in label.lower()
    assert "resume" in label.lower()


def test_document_fallback_uses_documents_not_pdf():
    files = [
        _fake_clustered_file("Reflection.pdf", "reflection"),
        _fake_clustered_file("Assessment.pdf", "analysis"),
    ]
    agent = FolderNamingAgent(max_examples=5, use_llm_fallback=False)
    label = agent.name_clusters(_build_cluster(files))[0]
    assert "pdf" not in label.lower()
