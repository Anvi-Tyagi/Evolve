"""Canonical list of India's 36 states/UTs and name normalisation.

`normalise()` maps known spelling variants onto one canonical name so joins with other
datasets do not silently drop states. Unknown names raise `UnknownStateError`; nothing
is guessed.
"""
import re

STATES = (
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa",
    "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala",
    "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland",
    "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
    "Uttar Pradesh", "Uttarakhand", "West Bengal",
)
UNION_TERRITORIES = (
    "Andaman and Nicobar Islands", "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu", "Delhi", "Jammu and Kashmir",
    "Ladakh", "Lakshadweep", "Puducherry",
)
CANONICAL_STATES = tuple(sorted(STATES + UNION_TERRITORIES))
assert len(CANONICAL_STATES) == 36

# Variants -> canonical name. Keys are written naturally; they are passed through
# `_key()` below, so case, '&' vs 'and', and punctuation do not matter.
_ALIASES = {
    # Andaman and Nicobar Islands
    "Andaman & Nicobar Island": "Andaman and Nicobar Islands",
    "Andaman and Nicobar": "Andaman and Nicobar Islands",
    "A&N Islands": "Andaman and Nicobar Islands",
    # Delhi
    "NCT of Delhi": "Delhi",
    "National Capital Territory of Delhi": "Delhi",
    "Delhi NCT": "Delhi",
    # Dadra and Nagar Haveli and Daman and Diu (merged 26 Jan 2020). The two former UTs
    # are mapped onto the merged UT; a dataset that still lists them separately will
    # produce two rows for the merged UT, which callers must aggregate (the validator
    # flags duplicate states).
    "UT of DNH and DD": "Dadra and Nagar Haveli and Daman and Diu",
    "DNH and DD": "Dadra and Nagar Haveli and Daman and Diu",
    "Dadra Nagar Haveli and Daman Diu": "Dadra and Nagar Haveli and Daman and Diu",
    "The Dadra and Nagar Haveli and Daman and Diu": "Dadra and Nagar Haveli and Daman and Diu",
    "Dadra and Nagar Haveli": "Dadra and Nagar Haveli and Daman and Diu",
    "Daman and Diu": "Dadra and Nagar Haveli and Daman and Diu",
    # Jammu and Kashmir
    "J&K": "Jammu and Kashmir",
    "Jammu Kashmir": "Jammu and Kashmir",
    # Former / alternative spellings
    "Orissa": "Odisha",
    "Pondicherry": "Puducherry",
    "Uttaranchal": "Uttarakhand",
    "Chattisgarh": "Chhattisgarh",
    "Tamilnadu": "Tamil Nadu",
}


class UnknownStateError(ValueError):
    """Raised when a name cannot be mapped to a canonical state/UT."""


def _key(name: str) -> str:
    s = name.upper().replace("&", " AND ")
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    return " ".join(s.split())


_LOOKUP = {_key(n): n for n in CANONICAL_STATES}
for _variant, _canonical in _ALIASES.items():
    assert _canonical in CANONICAL_STATES, _canonical
    _LOOKUP[_key(_variant)] = _canonical


def normalise(name: str) -> str:
    """Return the canonical state/UT name for `name`, or raise UnknownStateError."""
    if not isinstance(name, str) or not name.strip():
        raise UnknownStateError(f"Empty or non-string state name: {name!r}")
    try:
        return _LOOKUP[_key(name)]
    except KeyError:
        raise UnknownStateError(f"Unknown state/UT name: {name!r}") from None


def is_known(name: str) -> bool:
    try:
        normalise(name)
        return True
    except UnknownStateError:
        return False
