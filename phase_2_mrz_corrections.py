from phase_1_mrz_parser import parse_line2, verify_check_digits

"""
--------------------------------------------------------------------------------
                                       STAGE 1
--------------------------------------------------------------------------------
"""

# I created two dictionaries avoids OCR from confusing some specific characters. they undo mistakes after the fact

# letters that OCR mistakes for digits
mistaken_letters = {"O":"0", "D": "0", "I":"1", "Q":"0", "S":"5", "B":"8", "Z":"2", "G":"6"}
# digits that OCR mistakes for letters
mistaken_digits = {"0": "O", "1": "I", "5": "S", "8": "B", "2": "Z", "6": "G"}


"""
--------------------------------------------------------------------------------
                                       STAGE 2
--------------------------------------------------------------------------------
"""

# What kind of characters each MRZ field is allowed to hold.
# This tells the corrector which direction to fix in:
#   numeric --> any letter here is an OCR error, swap it for a digit
#   alpha   --> any digit here is an OCR error, swap it for a letter
#   mixed   --> both are legal, so no correction is safe
#
# Passport and personal numbers are mixed by design, so a "0" there may be a
# real zero or a misread "O". Guessing would corrupt valid data, so we leave
# them alone and let the check digits decide.

FIELD_TYPES = {
    "passport_number": "mixed",
    "passport_number_check": "numeric",
    "nationality": "alpha",
    "date_of_birth": "numeric",
    "date_of_birth_check": "numeric",
    "sex": "alpha",
    "expiration_date": "numeric",
    "expiration_date_check": "numeric",
    "personal_number": "mixed",
    "personal_number_check": "numeric",
    "composite_check": "numeric",
}

VERIFIABLE_FIELDS = {"passport_number", "date_of_birth",
                     "expiration_date", "personal_number"}

# The order the fields appear in line 2. Rebuilding must follow this exactly,
# or the line will not be 44 characters and nothing downstream will work.
FIELD_ORDER = [
    "passport_number", "passport_number_check", "nationality", "date_of_birth",
    "date_of_birth_check", "sex", "expiration_date", "expiration_date_check",
    "personal_number", "personal_number_check", "composite_check",
]


"""
--------------------------------------------------------------------------------
                                       STAGE 3
--------------------------------------------------------------------------------
"""

def correct_field(value: str, expected_type: str) -> tuple[str, list]:
    """
    Fix OCR substitutions in a field.

    expected_type is "numeric", "alpha", or "mixed"
    Returns the corrected value and a list of changes made
    """

    # Mixed fields hold both letters and digits, so we cannot tell a real "0"
    # from a misread "O". Leave them alone rather than corrupt good data.
    if expected_type == "mixed":
        return value, []

    # Numeric fields should hold digits only, so letters are the mistakes.
    elif expected_type == "numeric":
        table = mistaken_letters

    # Alpha fields should hold letters only, so digits are the mistakes.
    elif expected_type == "alpha":
        table = mistaken_digits

    else:
        raise ValueError(f"Unknown field type: {expected_type!r}")

    chars = []      # the fixed characters, joined into a string at the end
    changes = []    # a record of every swap we made

    for index, char in enumerate(value):

        # "<" is padding, never an error. Keep it exactly as it is.
        if char == "<":
            chars.append(char)
            continue

        # Is this character already the kind this field expects?
        if expected_type == "numeric":
            already_correct = char.isdigit()
        else:
            already_correct = "A" <= char <= "Z"

        # Nothing to fix, so keep it and move on.
        if already_correct:
            chars.append(char)
            continue

        # Wrong kind, and we know the usual fix. Swap it and note what changed.
        if char in table:
            new_char = table[char]
            chars.append(new_char)
            changes.append({"position": index, "from": char, "to": new_char})
            continue

        # Wrong kind, but not a mistake we recognise. Keep it unchanged and let
        # the check digits catch it. Guessing here would hide a real problem.
        else:
            chars.append(char)

    # Glue the characters back into one string and hand back both results.
    return "".join(chars), changes


"""
--------------------------------------------------------------------------------
                                       STAGE 4
--------------------------------------------------------------------------------
"""

def correct_some_fields(fields: dict, field_names) -> tuple[dict, list]:
    """
    Correct only the named fields, leaving the rest as they are.

    Returns a full set of fields (corrected and untouched together)
    and the list of changes made.
    """
    corrected = dict(fields)   # start from a copy of everything
    changes_made = []

    for field_name in field_names:
        value = fields[field_name]
        field_type = FIELD_TYPES[field_name]
        fixed, changes = correct_field(value, field_type)
        corrected[field_name] = fixed

        for change in changes:
            change["field"] = field_name

        changes_made.extend(changes)

    return corrected, changes_made


def build_and_score(fields: dict) -> tuple[str, dict, int]:
    """Glue fields back into a 44-character line and score its check digits."""
    line = "".join(fields[name] for name in FIELD_ORDER)

    if len(line) != 44:
        raise ValueError(f"Rebuilt line is {len(line)} characters, expected 44")

    checks = verify_check_digits(line, parse_line2(line))
    return line, checks, sum(checks.values())


def correct_line2(line2: str) -> dict:
    """
    Repair OCR errors in line 2 of the MRZ.

    Corrections split into two kinds. Fields with no check digit cannot be
    verified, but a type violation there is certainly wrong, so those fixes
    are always applied. Fields with a check digit are guesses, so those fixes
    are only kept if they make more checks pass.
    """

    fields = parse_line2(line2)
    original = verify_check_digits(line2, fields)

    # Group the fields by whether a check digit can prove them.
    unverifiable = [n for n in FIELD_ORDER if n not in VERIFIABLE_FIELDS]
    verifiable = [n for n in FIELD_ORDER if n in VERIFIABLE_FIELDS]

    # Pass 1 — certain fixes. Always kept.
    safe_fields, safe_changes = correct_some_fields(fields, unverifiable)
    safe_line, safe_checks, safe_score = build_and_score(safe_fields)

    # Pass 2 — guesses, applied on top of the safe version.
    full_fields, risky_changes = correct_some_fields(safe_fields, verifiable)
    full_line, full_checks, full_score = build_and_score(full_fields)

    # Keep the guesses only if they actually helped.
    improved = full_score > safe_score

    return {
        "line": full_line if improved else safe_line,
        "improved": improved,
        "changes": safe_changes + risky_changes if improved else safe_changes,
        "before": original,
        "after": full_checks if improved else safe_checks,
    }