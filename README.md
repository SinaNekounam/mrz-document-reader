# MRZ Document Reader

Reads the two machine-readable lines at the bottom of a passport and checks them
for errors. Give it a photo, get back the name, document number, dates and
nationality — plus how much each one can be trusted.

This is the document-reading part of the FinPay KYC scope (sections 5.3 and 5.4).
It does not do face matching, liveness, risk scoring, or forgery detection.

**Read [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) before relying on any
result.** A good forgery with correct check digits would pass every test here.

---

## How it works

The MRZ carries **check digits** — numbers worked out from the data itself. If a
character is misread, the maths stops adding up, so the error can be caught.

1. Crop the bottom strip of the image and clean it up.
2. Run OCR, restricted to the characters an MRZ can contain.
3. Repair common OCR mistakes (`O` for `0`, `I` for `1`, and so on).
4. Recalculate the check digits. Keep a repair only if more checks now pass.
5. Turn the values into readable form — real dates, padding removed.

Because a repair is only kept when it improves the maths, the reader never
reports a fix it cannot back up.

### Confidence

| Level | Meaning |
|---|---|
| `high` | A check digit proves it, and nothing was changed. |
| `medium` | A check digit proves it, but an OCR error was repaired first. |
| `low` | The check digit failed, **or there is no check digit for this field**. |

Nationality, sex and the names are always `low` — the MRZ has no way to verify
them, however correct they look.

---

## Setup

**1. Install Tesseract.** It is a separate program, not a Python package.

- Windows: [UB Mannheim installer](https://github.com/UB-Mannheim/tesseract/wiki)
- macOS: `brew install tesseract`
- Linux: `sudo apt install tesseract-ocr`

**2. Point the code at it.** In `phase_3_mrz_ocr.py`:

```python
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
```

On macOS and Linux this is usually already on the PATH.

**3. Install the packages.**

```bash
pip install -r requirements.txt
```

---

## Running it

Start the API:

```bash
uvicorn main:app --reload
```

Open **http://127.0.0.1:8000/docs** to upload an image and see the result.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Is the service running? |
| `POST` | `/api/v1/mrz/read` | Read the MRZ from an uploaded image. |

An unreadable document returns 422 with a reason.

Or from Python:

```python
from phase_4_mrz_models import TesseractProvider

result = TesseractProvider().extract("specimen.jpg")
print(result.fields["date_of_birth"].normalized)
```

Run the tests:

```bash
pytest
```

---

## Output

```json
{
  "raw_line2": "RC00150586UT09105045F2509013<99999000T<<<<82",
  "fields": {
    "passport_number": {
      "raw": "RC0015058",
      "normalized": "RC0015058",
      "confidence": "high",
      "valid": true
    },
    "date_of_birth": {
      "raw": "910504",
      "normalized": "1991-05-04",
      "confidence": "high",
      "valid": true
    },
    "nationality": {
      "raw": "UTO",
      "normalized": "UTO",
      "confidence": "low",
      "valid": null
    }
  },
  "all_checks_passed": true,
  "corrections": [
    { "field": "nationality", "position": 2, "from": "0", "to": "O" }
  ]
}
```

`raw_line1` and `raw_line2` hold exactly what the OCR engine saw, before any
repair — note the `UT0` with a zero, which the `corrections` list shows being
fixed to `UTO`.

`valid` is `null` where the field has no check digit.

---

## Files

| File | Contents |
|---|---|
| `phase_1_mrz_parser.py` | Check-digit maths and field positions |
| `phase_2_mrz_corrections.py` | OCR error correction |
| `phase_3_mrz_ocr.py` | Image handling and OCR |
| `phase_4_mrz_models.py` | Output format and provider interface |
| `main.py` | The API |
| `test_corrections.py`, `test_models.py` | Tests |
| `specimen.jpg` | Specimen passport used for testing |

---

## Swapping the OCR engine

All Tesseract code sits behind one interface in `phase_4_mrz_models.py`:

```python
class OCRProvider(ABC):
    @abstractmethod
    def extract(self, image_path: str) -> MRZResult: ...
```

To use a commercial provider, write a class that inherits from it and implements
`extract`. Nothing else changes — the parsing, correction and verification are
engine-independent.

---

## Supported formats

Only **TD3** passports: two lines of 44 characters. TD1 and TD2 identity cards
are rejected with an error rather than parsed incorrectly.

---

## Test data

Only published specimen documents with fictional data were used. No real
identity document was processed, as required by section 10.2 of the scope.
