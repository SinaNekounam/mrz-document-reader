# Known Limitations

This document records what the MRZ Document Reader does **not** do, and where its
results should not be relied on. It is written in response to section 13.2 of the
FinPay KYC Technical Scope, which requires that open-source OCR and heuristic
capabilities are accurately classified and not presented as certified verification.

---

## 1. Classification of this component

This module performs **machine-readable zone (MRZ) extraction and arithmetic
validation only**. It is not an identity verification system.

It does not, and does not claim to:

- verify that a document is genuine
- detect forgery, tampering, or digitally altered images
- check any field against a government or issuing-authority database
- confirm that the document belongs to the person presenting it

A passing result means the MRZ was read and its check digits are internally
consistent. A well-made forgery with correctly calculated check digits would
pass every test in this module.

---

## 2. OCR engine

Text is extracted using **Tesseract**, an open-source OCR engine. Tesseract is
general-purpose software, not a certified document-reading product, and has not
been independently validated for identity document use.

Observed behaviour:

- Runs of `<` padding are frequently misread as `K`, and occasionally as `E` or `S`,
  because adjacent chevrons touch at the resolution used.
- Accuracy depends heavily on image quality. All results below were obtained from
  a flat, straight-on, well-lit specimen scan.

Replacing Tesseract with a commercial provider requires implementing the
`OCRProvider` interface. No other code changes are needed.

---

## 3. Supported document formats

| Format | Layout | Supported |
|---|---|---|
| TD3 | 2 lines of 44 characters (passport booklet) | Yes |
| TD2 | 2 lines of 36 characters (ID card) | No |
| TD1 | 3 lines of 30 characters (ID card) | No |

Line length is validated strictly. A TD1 or TD2 document raises a `ValueError`
rather than being parsed incorrectly — the failure is loud, not silent.

Adding TD1 and TD2 support requires a format detector and additional
field-position tables. The parsing, correction, and verification logic is
format-independent and would be reused unchanged.

---

## 4. Image handling

The MRZ is located by cropping a **fixed fraction of the image** (bottom ~24%,
with ~2% trimmed from each side). These values are tuned to one specimen image.

Consequences:

- Photographs taken at an angle, rotated, or with significant perspective
  distortion are likely to fail.
- Documents photographed at a different distance or framing may be cropped
  incorrectly, producing partial or empty lines.
- No deskewing, perspective correction, or automatic MRZ detection is performed.

A production implementation would locate the MRZ by content rather than by fixed
position.

---

## 5. Errors that cannot be detected

### Line 1 is unverified

MRZ line 1 contains the document type, issuing country, and name. **It carries no
check digits.** No arithmetic test can confirm it was read correctly.

The test specimen demonstrates this: the surname is read as `CITIZENK` instead of
`CITIZEN`. The extra character is an OCR error inside the name field. It is not
detected, not corrected, and not flagged, because nothing in the MRZ standard
makes it detectable.

Structural repair is applied to line 1's **padding region only** — the chevrons
after the name. Characters within the name itself are never altered, because an
unverifiable guess is worse than a known-unreliable value.

### Digit-for-digit errors

The correction system repairs characters that OCR commonly confuses between
letters and digits (`O`/`0`, `I`/`1`, `S`/`5`, `B`/`8`, `Z`/`2`, `G`/`6`, `D`/`0`,
`Q`/`0`). It cannot repair a digit misread as a *different digit* — for example
`740812` read as `740813`. Such errors cause the check digit to fail, and the
field is correctly reported as invalid rather than silently repaired.

### Mixed-content fields

Passport number and personal number may legitimately contain both letters and
digits. No correction is attempted on these fields, because a `0` there may be a
genuine zero or a misread `O` and there is no way to distinguish them. Errors in
these fields are caught by their check digits but cannot be automatically fixed.

---

## 6. Date interpretation

MRZ dates store only two digits of the year. The century is inferred, not read:

- **Birth dates**: a date that would fall in the future is assigned to the 1900s.
- **Expiry dates**: a date more than 20 years ahead is assigned to the 1900s.

These are conventions, not facts recorded in the document. A person born in 1926
would be misinterpreted as born in 2026 under the birth-date rule.

Dates that are structurally impossible (month 13, 31 February) return no parsed
value rather than raising an error.

---

## 7. Confidence values

Confidence reflects **verifiability, not plausibility**:

| Level | Meaning |
|---|---|
| `high` | A check digit proves the field, and no character was changed. |
| `medium` | A check digit proves the field, but an OCR error was repaired first. |
| `low` | The check digit failed, **or the field has no check digit at all**. |

Fields with no check digit — nationality, sex, document type, and all name
fields — are always `low`, even when the value is almost certainly correct. This
is deliberate. Reporting a plausible-looking but unprovable value as high
confidence would misrepresent what this module can establish.

---

## 8. Raw value storage

The `raw` value on each field is currently the value **after** correction, not the
original OCR output. The uncorrected lines are preserved in `raw_line1` and
`raw_line2` on the result object, so the original is recoverable, but per-field
raw values do not yet distinguish pre- and post-correction state.

Section 5.3 of the scope requires both to be stored per field. This is a known
gap.

---

## 9. Not implemented

The following are outside the scope of this module and are not present in any
form:

- Image quality scoring (blur, glare, resolution thresholds) — section 5.2
- Document authenticity and forgery heuristics — section 5.4
- Face extraction and comparison — section 6.1
- Liveness and anti-spoofing — section 6.2
- Duplicate and reuse detection — section 6.3
- Risk scoring and decision routing — section 7
- Malware scanning of uploaded files — section 5.1
- Persistent storage, audit logging, and retention — sections 9 and 10
- Authentication, authorization, and rate limiting on the API — section 10.1

The API currently accepts any upload without authentication and performs no file
validation beyond what the image decoder enforces. It is suitable for local
evaluation only, not for deployment.

---

## 10. Test data

All development and testing used **published specimen documents** containing
fictional data. No real identity document was processed at any point, in line
with section 10.2 of the scope.
