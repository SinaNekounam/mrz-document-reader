from phase_2_mrz_corrections import correct_field, correct_line2
from phase_4_mrz_models import TesseractProvider

CLEAN = "L898902C36UTO7408122F1204159ZE184226B<<<<<10"


def test_numeric_field_swaps_letters():
    fixed, changes = correct_field("74O8I2", "numeric")
    assert fixed == "740812"
    assert len(changes) == 2


def test_alpha_field_swaps_digits():
    fixed, changes = correct_field("UT0", "alpha")
    assert fixed == "UTO"
    assert len(changes) == 1


def test_mixed_field_is_never_touched():
    fixed, changes = correct_field("L8989O2C3", "mixed")
    assert fixed == "L8989O2C3"
    assert changes == []


def test_filler_survives():
    fixed, changes = correct_field("<<<<<", "numeric")
    assert fixed == "<<<<<"
    assert changes == []


def test_unknown_character_left_alone():
    fixed, changes = correct_field("74A812", "numeric")
    assert fixed == "74A812"
    assert changes == []


def test_clean_line_needs_no_repair():
    result = correct_line2(CLEAN)
    assert result["improved"] is False
    assert result["changes"] == []


def test_ocr_errors_are_repaired():
    dirty = "L898902C36UTO74O8I22F12O4I59ZE184226B<<<<<10"
    result = correct_line2(dirty)
    assert result["line"] == CLEAN
    assert result["improved"] is True


def test_real_typo_is_not_faked():
    """A wrong digit is not an OCR lookalike, so it must stay broken."""
    broken = "L898902C36UTO7408132F1204159ZE184226B<<<<<10"
    result = correct_line2(broken)
    assert result["line"] == broken
    assert result["improved"] is False

def test_unverifiable_field_is_always_fixed():
    """Nationality has no check digit, but a digit there is certainly wrong,
    so the fix must survive even though the score cannot improve."""
    dirty = "RC00150586UT09105045F2509013<99999000T<<<<82"
    result = correct_line2(dirty)
    assert "UTO" in result["line"]
    assert len(result["changes"]) == 1