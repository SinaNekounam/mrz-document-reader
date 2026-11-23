def char_value(char: str) -> int:
    """Convert one MRZ character to its numeric value.
    Digits -> themselves (e.g. '7' -> 7)
    Letters -> 10 to 35   (A -> 10, B -> 11 ... Z -> 35)
    '<'     -> 0
    """

    if char.isdigit():
        return int(char)
    elif char == "<":
        return 0
    elif "A" <= char <= "Z":
        return ord(char) - ord("A") + 10
    else:
        raise ValueError(f"Invalid character: {char!r}")


def check_digit(field: str) -> int:
    """Calculate the ICAO check digit for an MRZ field."""
    weights = [7, 3, 1]
    total = 0

    for index, char in enumerate(field):
        # get the character's value
        value = char_value(char)
        # pick the right weight using index and the modulo operator
        weight = weights[index % 3]
        # add value * weight to total
        total += value * weight

    # return the last digit of total
    return total % 10

def parse_line2(line: str) -> dict:
    fields = {}

    if len(line) != 44:
        raise ValueError(f"Line 2 must be 44 characters, got {len(line)}")

    fields["passport_number"] = line[0:9]
    fields["passport_number_check"] = line[9]
    fields["nationality"] = line[10:13]
    fields["date_of_birth"] = line[13:19]
    fields["date_of_birth_check"] = line[19]
    fields["sex"] = line[20]
    fields["expiration_date"] = line[21:27]
    fields["expiration_date_check"] = line[27]
    fields["personal_number"] = line[28:42]
    fields["personal_number_check"] = line[42]
    fields["composite_check"] = line[43]

    return fields

def parse_line1(line: str) -> dict:
    if len(line) != 44:
        raise ValueError(f"Line 1 must be 44 characters, got {len(line)}")

    document_type = line[0]
    issuing_country = line[2:5]
    name_field = line[5:44]
    parts = name_field.split("<<")

    surname = parts[0]
    surname = surname.strip("<")
    surname = surname.replace("<", " ")

    given_name = parts[1] if len(parts) > 1 else ""

    given_name = given_name.strip("<")
    given_name = given_name.replace("<", " ")

    return {
        "document_type": document_type,
        "issuing_country": issuing_country,
        "surname": surname,
        "given_names": given_name,
    }

def stored_digit(value: str) -> int | None:
    """
    Read a check digit from the MRZ.

    A check digit must be a digit. If OCR gave us a letter, the position is
    unreadable — that is a failed check, not a crash and not a pass.
    """
    return int(value) if value.isdigit() else None

def verify_check_digits(line2: str, fields: dict) -> dict:

    pairs = [
        ("passport_number", "passport_number_check"),
        ("date_of_birth", "date_of_birth_check"),
        ("expiration_date", "expiration_date_check"),
        ("personal_number", "personal_number_check"),
    ]

    results = {}
    for field_name, check_name in pairs:
        calculated = check_digit(fields[field_name])
        stored = stored_digit(fields[check_name])
        results[field_name] = stored is not None and calculated == stored

    composite_field = line2[0:10] + line2[13:20] + line2[21:43]
    composite_stored = stored_digit(line2[43])
    results["composite"] = (
            composite_stored is not None
            and check_digit(composite_field) == composite_stored
    )

    return results

if __name__ == "__main__":

    print(check_digit("L898902C3"))  # expect 6
    print(check_digit("740812"))  # expect 2
    print(check_digit("120415"))  # expect 9

    line2 = "L898902C36UTO7408122F1204159ZE184226B<<<<<10"
    for key, value in parse_line2(line2).items():
        print(key, "=", value)

    print(line2)
    fields = parse_line2(line2)
    print(verify_check_digits(line2, fields))