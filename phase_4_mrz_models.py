from pydantic import BaseModel
from typing import Literal
from datetime import datetime
from datetime import date

from abc import ABC, abstractmethod

from phase_3_mrz_ocr import read_mrz

# Check digits are proof, not data. They are recorded in each field's
# "valid" flag rather than listed as fields in their own right.
CHECK_DIGIT_FIELDS = {
    "passport_number_check",
    "date_of_birth_check",
    "expiration_date_check",
    "personal_number_check",
    "composite_check",
}


"""
-------------------------------------------------------------------------------------------------------
                                            STAGE 1
-------------------------------------------------------------------------------------------------------
"""

class MRZField(BaseModel):
    raw: str
    normalized: str
    confidence: Literal["high", "medium", "low"]
    valid: bool | None = None
    source: str = "tesseract"

confidence: Literal["high", "medium", "low"]

"""
-------------------------------------------------------------------------------------------------------
                                            STAGE 2
-------------------------------------------------------------------------------------------------------
"""

class MRZResult(BaseModel):
    # The two lines exactly as OCR produced them, before any repair.
    # Kept so a reviewer can see what the engine actually saw.
    raw_line1: str
    raw_line2: str

    # The fields, each with its own raw value, normalized value and confidence.
    fields: dict[str, MRZField]

    # Did every check digit pass?
    all_checks_passed: bool

    # What we changed, and why. Needed for the audit trail.
    corrections: list[dict] = []

    status: Literal["OCR_COMPLETED", "PROCESSING_ERROR"] = "OCR_COMPLETED"
    processed_at: datetime
    provider: str = "tesseract"
    provider_version: str = ""


"""
-------------------------------------------------------------------------------------------------------
                                            STAGE 3
-------------------------------------------------------------------------------------------------------
"""

def parse_mrz_date(value: str, is_birth_date: bool) -> date | None:
    """
    Turn a six-digit MRZ date (YYMMDD) into a real date.

    The century is not stored in an MRZ, so we work it out:
    a birth date cannot be in the future, and an expiry date is not
    decades away.

    Returns None if the value is not a usable date.
    """

    # reject anything that is not exactly 6 digits
    if len(value) != 6 or not value.isdigit():
        return None

    # split into year, month, day
    year = int(value[0:2])
    month = int(value[2:4])
    day = int(value[4:6])

    # work out the century
    current_yy = date.today().year % 100

    if is_birth_date:
        # A birth date cannot be in the future.
        if year > current_yy:
            full_year = 1900 + year
        else:
            full_year = 2000 + year
    else:
        # An expiry can be a decade ahead, so allow a window before
        # assuming the previous century.
        if year > current_yy + 20:
            full_year = 1900 + year
        else:
            full_year = 2000 + year

    # build the date, catching the case where it is not a real date
    # (month 13, day 31 in February, and so on)
    try:
        return date(full_year, month, day)
    except ValueError:
        return None

"""
-------------------------------------------------------------------------------------------------------
                                            STAGE 4
-------------------------------------------------------------------------------------------------------
"""
def assess_confidence(field_name: str, valid: bool | None, was_corrected: bool) -> str:
    """
    Rate how much we trust a field.

    high   — a check digit proves it, and nothing had to be changed
    medium — a check digit proves it, but only after repairing an OCR error
    low    — the check digit failed, or this field has no check digit at all

    Fields with no check digit are always low, even when the correction was
    almost certainly right. Confidence here means verified, not plausible.
    """

    # no check digit exists -> "low"
    if valid is None:
        return "low"

    # check digit failed -> "low"
    if valid is False:
        return "low"

    # passed but corrected -> "medium"
    if was_corrected:
        return "medium"

    # passed and untouched -> "high"
    return "high"


"""
-------------------------------------------------------------------------------------------------------
                                            STAGE 5
-------------------------------------------------------------------------------------------------------
"""
def normalize(field_name: str, value: str) -> str:
    """
    Clean a raw MRZ value into something readable.

    Raw MRZ values carry padding and compressed dates. This turns them
    into the form a person or another system would expect.
    """

    # Dates are YYMMDD with no century. parse_mrz_date works it out.
    if field_name == "date_of_birth":
        parsed = parse_mrz_date(value, is_birth_date=True)
        return parsed.isoformat() if parsed else ""

    if field_name == "expiration_date":
        parsed = parse_mrz_date(value, is_birth_date=False)
        return parsed.isoformat() if parsed else ""

    # "<" means unspecified, not a literal character.
    if field_name == "sex":
        return "X" if value == "<" else value

    # These are padded on the right to a fixed width.
    if field_name in ("passport_number", "personal_number", "surname", "given_names"):
        return value.replace("<", " ").strip()

    # Everything else is already usable.
    return value


class OCRProvider(ABC):
    """
    The contract every OCR engine must satisfy.

    Nothing outside this file knows which engine is in use. To add a
    commercial provider later, write a new class that inherits from this
    and implements extract(). No other code changes.
    """

    @abstractmethod
    def extract(self, image_path: str) -> MRZResult:
        """Read the MRZ from an image and return the normalized result."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """The provider's name, recorded on every result."""
        ...


class TesseractProvider(OCRProvider):
    """Reads the MRZ using the open-source Tesseract engine."""

    @property
    def name(self) -> str:
        return "tesseract"

    def extract(self, image_path: str) -> MRZResult:
        # Step 1: run the Phase 3 pipeline
        raw = read_mrz(image_path)

        # Step 2: work out which fields were corrected
        corrected_names = {c["field"] for c in raw["corrections"]}

        # Step 3: build one MRZField per field
        fields = {}
        for field_name, value in raw["fields"].items():

            if field_name in CHECK_DIGIT_FIELDS:
                continue

            valid = raw["checks"].get(field_name)

            was_corrected = field_name in corrected_names

            fields[field_name] = MRZField(
                raw = value,
                normalized = normalize(field_name, value),
                confidence = assess_confidence(field_name, valid, was_corrected),
                valid = valid,
                source = self.name,
            )

        # Step 4: wrap it all up
        return MRZResult(
            raw_line1=raw["ocr_line1"],
            raw_line2=raw["ocr_line2"],
            fields = fields,
            all_checks_passed = raw["all_checks_passed"],
            corrections = raw["corrections"],
            processed_at = datetime.now(),
            provider = self.name,
        )



