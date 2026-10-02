"""Offline licensing: a signed receipt, verified locally, with no phone-home.

Everything in EDIFY works with no network. A licence check is not going to be the
one exception, so the token carries its own proof and the verification is a
signature check against an embedded public key.
"""

from .tier import (
    PLANS,
    RETIRED_PLANS,
    Entitlement,
    clear,
    current,
    license_path,
    save,
)
from .token import License, issue, parse

__all__ = [
    "Entitlement",
    "License",
    "PLANS",
    "RETIRED_PLANS",
    "clear",
    "current",
    "issue",
    "license_path",
    "parse",
    "save",
]
