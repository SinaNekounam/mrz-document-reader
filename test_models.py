from pathlib import Path

from phase_4_mrz_models import TesseractProvider

# Find specimen.jpg next to this test file, wherever pytest is run from.
SPECIMEN = str(Path(__file__).parent / "specimen.jpg")


def test_provider_returns_normalized_fields():
    """One test covering the whole pipeline: image, OCR, correction,
    verification and normalization."""
    result = TesseractProvider().extract(SPECIMEN)

    assert result.fields["date_of_birth"].normalized == "1991-05-04"
    assert result.fields["expiration_date"].normalized == "2025-09-01"
    assert result.fields["passport_number"].normalized == "RC0015058"
    assert result.fields["nationality"].normalized == "UTO"
    assert result.all_checks_passed is True


def test_check_digits_are_not_listed_as_fields():
    result = TesseractProvider().extract(SPECIMEN)
    assert "passport_number_check" not in result.fields


def test_confidence_reflects_verifiability():
    result = TesseractProvider().extract(SPECIMEN)
    # Proven by a check digit, nothing changed.
    assert result.fields["passport_number"].confidence == "high"
    # No check digit exists, so it cannot be verified however likely it looks.
    assert result.fields["nationality"].confidence == "low"