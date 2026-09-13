"""
Offline-safe tests for the PRD AI modules: Urgency Assessment, Consistency
Engine / Abuse Pattern Detection, and Duplicate Detection. The rule-based
pieces (no LLM/Pinecone needed) are tested directly; anything requiring a
live API degrades gracefully and is tested only for that graceful path.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai.schemas import SeverityAssessment, VerificationFlag, safe_validate
from ai.verification import check_low_detail
from ai.duplicate_detector import find_duplicates, index_report
from rag import pinecone_client


def test_severity_assessment_schema():
    result = safe_validate(SeverityAssessment, {"severity": "Critical", "reason": "Weapon mentioned"})
    assert isinstance(result, SeverityAssessment)
    assert result.severity == "Critical"

    # Invalid severity level must be rejected, not silently accepted.
    assert safe_validate(SeverityAssessment, {"severity": "Extreme", "reason": "x"}) is None


def test_verification_flag_schema():
    flag = safe_validate(VerificationFlag, {
        "flag_type": "inconsistency", "message": "Dates don't match.", "severity": "warning",
    })
    assert isinstance(flag, VerificationFlag)


def test_check_low_detail_flags_sparse_report():
    flags = check_low_detail("stolen", [])
    assert len(flags) == 1
    assert flags[0].flag_type == "low_detail"


def test_check_low_detail_allows_detailed_report():
    flags = check_low_detail(
        "Someone broke into my car outside the shopping center around 9pm and took my phone and wallet.",
        [{"question": "Was anyone injured?", "answer": "No"}],
    )
    assert flags == []


def test_check_low_detail_flags_many_skips():
    qa = [{"question": f"Q{i}", "answer": "Not provided"} for i in range(4)]
    flags = check_low_detail("A reasonably detailed description of what happened here.", qa)
    assert any(f.flag_type == "low_detail" for f in flags)


def test_duplicate_detection_degrades_without_pinecone():
    if pinecone_client.is_available():
        # Live path: should not raise, and indexing then finding should work.
        index_report("TEST-DUP-1", "Theft / Pickpocketing", "My wallet was stolen from my bag at the market.")
        matches = find_duplicates("Theft / Pickpocketing", "My wallet was stolen from my bag at the market.")
        assert isinstance(matches, list)
    else:
        assert find_duplicates("Theft / Pickpocketing", "anything") == []


if __name__ == "__main__":
    test_severity_assessment_schema()
    test_verification_flag_schema()
    test_check_low_detail_flags_sparse_report()
    test_check_low_detail_allows_detailed_report()
    test_check_low_detail_flags_many_skips()
    test_duplicate_detection_degrades_without_pinecone()
    print("Verification/severity/duplicate tests passed.")
