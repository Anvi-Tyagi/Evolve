import pytest

from evolve.states import CANONICAL_STATES, UnknownStateError, is_known, normalise


def test_36_unique_canonical_names():
    assert len(CANONICAL_STATES) == 36
    assert len(set(CANONICAL_STATES)) == 36


@pytest.mark.parametrize("name", CANONICAL_STATES)
def test_canonical_round_trip(name):
    assert normalise(name) == name
    assert normalise(name.upper()) == name
    assert normalise(f"  {name.lower()}  ") == name


@pytest.mark.parametrize(
    "variant, expected",
    [
        ("ANDAMAN & NICOBAR ISLAND", "Andaman and Nicobar Islands"),
        ("Andaman & Nicobar Islands", "Andaman and Nicobar Islands"),
        ("Andaman and Nicobar", "Andaman and Nicobar Islands"),
        ("NCT of Delhi", "Delhi"),
        ("DELHI", "Delhi"),
        ("UT OF DNH AND DD", "Dadra and Nagar Haveli and Daman and Diu"),
        ("Dadra & Nagar Haveli and Daman & Diu", "Dadra and Nagar Haveli and Daman and Diu"),
        ("Daman and Diu", "Dadra and Nagar Haveli and Daman and Diu"),
        ("J&K", "Jammu and Kashmir"),
        ("JAMMU AND KASHMIR", "Jammu and Kashmir"),
        ("Orissa", "Odisha"),
        ("Pondicherry", "Puducherry"),
        ("Uttaranchal", "Uttarakhand"),
        ("Tamilnadu", "Tamil Nadu"),
    ],
)
def test_variants(variant, expected):
    assert normalise(variant) == expected


@pytest.mark.parametrize("bad", ["Atlantis", "", "   ", None, 42, "Delhii", "New Delhi"])
def test_unknown_raises(bad):
    with pytest.raises(UnknownStateError):
        normalise(bad)
    assert not is_known(bad)


def test_all_csv_state_names_are_known():
    """Every raw name in the real exports must map to a distinct canonical state."""
    import csv
    from evolve.config import DATA_DIR, YEARS, FILE_PATTERN

    for year in YEARS:
        with open(DATA_DIR / FILE_PATTERN.format(year=year), newline="") as f:
            names = [row["state"] for row in csv.DictReader(f)]
        assert sorted({normalise(n) for n in names}) == sorted(CANONICAL_STATES)
