"""
Phase 3 — Read the MRZ from a passport image.

Takes an image file, finds the two MRZ lines, and returns the verified fields.
"""

import cv2
import pytesseract

from phase_1_mrz_parser import parse_line1, parse_line2, verify_check_digits
from phase_2_mrz_corrections import correct_line2


# --- Configuration -----------------------------------------------------------

TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# The MRZ sits in the bottom strip of the page. These fractions are tuned to
# a straight-on scan and will need adjusting for photos taken at an angle.
CROP_TOP = 0.76
CROP_BOTTOM = 0.97
CROP_LEFT = 0.03
CROP_RIGHT = 0.99

# psm 6 treats the image as one uniform block of text, which the MRZ is.
# The whitelist stops Tesseract inventing characters an MRZ cannot contain.
TESSERACT_CONFIG = (
    "--psm 6 -c tessedit_char_whitelist="
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<"
)

PADDING_CHARS = "<KES"

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


# --- Steps -------------------------------------------------------------------

def load_image(path: str):
    """Load an image, failing loudly if the file is missing."""
    image = cv2.imread(path)
    if image is None:
        raise FileNotFoundError(f"Could not load the image: {path}")

    return image


def crop_to_mrz(image):
    """Cut the image down to the strip where the MRZ sits."""
    height, width = image.shape[:2]

    top = int(height * CROP_TOP)
    bottom = int(height * CROP_BOTTOM)
    left = int(width * CROP_LEFT)
    right = int(width * CROP_RIGHT)

    return image[top:bottom, left:right]


def clean_for_ocr(mrz_area):
    """Greyscale, enlarge and threshold so Tesseract can read the text."""
    grey = cv2.cvtColor(mrz_area, cv2.COLOR_BGR2GRAY)

    # The characters are small, and Tesseract reads taller text better.
    grey = cv2.resize(grey, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    # Force every pixel to pure black or pure white.
    # This removes the patterned background printed behind the text.
    _, binary = cv2.threshold(grey, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    cv2.imwrite("cleaned.jpg", binary)

    return binary


def read_lines(binary) -> list:
    """Run OCR and return only the lines long enough to be MRZ lines."""

    text = pytesseract.image_to_string(binary, config=TESSERACT_CONFIG)

    # Tesseract returns one string with newlines in it. Split it, tidy each
    # line, and drop anything too short to be an MRZ line — the page edge
    # often produces a line or two of junk.
    raw_lines = [line.strip() for line in text.strip().split("\n")]
    return [line for line in raw_lines if len(line) >= 40]


def repair_line1(line: str) -> str:
    """
    Repair OCR damage in the padding region of MRZ line 1.

    Line 1 has no check digits, so it cannot be verified mathematically.
    But its structure is known: a name, then "<" padding out to 44 characters.
    Tesseract reads runs of "<" as "K", "E" or "S", so we find where the
    padding starts and rewrite everything after it.
    """

    # Step 1: find the separator
    separator = line.find("<<")
    if separator == -1:
        return line  # cannot locate the name, do not guess

    # Step 2: start searching after the separator
    start = separator + 2

    # Step 3: find where padding begins
    cut_at = None
    for i in range(start, len(line) - 2):
        chunk = line[i:i + 3]
        # Real padding always starts with a genuine "<". Tesseract only
        # misreads chevrons in the middle of a run, where they touch.
        # Requiring the first character to be "<" stops a real "E" or "S"
        # at the end of a name being mistaken for padding.
        if chunk[0] == "<" and all(c in PADDING_CHARS for c in chunk):
            cut_at = i
            break

    # Step 4: if no padding run was found, the line is all name — leave it
    if cut_at is None:
        return line.ljust(44, "<")

    # Step 5: cut and pad
    core = line[:cut_at]
    return core.ljust(44, "<")


# --- The whole pipeline ------------------------------------------------------

def read_mrz(image_path: str) -> dict:
    """
    Read and verify the MRZ from a passport image.

    Returns the extracted fields and the check digit results.
    """
    image = load_image(image_path)
    mrz_area = crop_to_mrz(image)
    binary = clean_for_ocr(mrz_area)
    lines = read_lines(binary)

    if len(lines) < 2:
        raise ValueError(f"Expected 2 MRZ lines, found {len(lines)}")

    line1 = repair_line1(lines[0])
    result = correct_line2(lines[1])

    fields = parse_line1(line1)
    fields.update(parse_line2(result["line"]))
    checks = verify_check_digits(result["line"], fields)

    return {
        "ocr_line1": lines[0],
        "ocr_line2": lines[1],
        "line1": line1,
        "line2": result["line"],
        "fields": fields,
        "checks": checks,
        "all_checks_passed": all(checks.values()),
        "corrections": result["changes"],
    }


if __name__ == "__main__":
    output = read_mrz("specimen.jpg")
    for key, value in output.items():
        print(key, "=", value)

#--------------------------------------------------------------------------------------------
