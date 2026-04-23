from backend.agents.identity_utils import build_identity_text, clean_filename, infer_doctype


def test_clean_filename_strips_known_noise():
    assert clean_filename("Resume - Google Docs_final (1)") == "Resume"


def test_infer_doctype_uses_filename_and_content():
    doctype = infer_doctype(
        "Thomas Parisi Resume",
        "Thomas Parisi software developer python projects and experience"
    )
    assert doctype == "resume"


def test_build_identity_text_prepends_doctype():
    identity = build_identity_text(
        "University Health Plan - Google Docs.pdf",
        "University health plan coverage eligibility deductible benefits"
    )
    assert identity.startswith("agreement: ")
