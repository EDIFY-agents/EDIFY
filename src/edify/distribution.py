"""The names this package is published and found under.

Written once, so that `selfinstall`, `governance`, `feedback`, `assets` and `errors`
cannot disagree about them. The old third-party name is deliberately absent: it
belongs to another project, and a name that is not here cannot be reached by
`self update`.
"""

#: The public edition on PyPI. `pyproject.toml` spells the same string on one line,
#: because `selfinstall.is_source_checkout` reads it literally.
DIST_NAME = "edify-agents-cli"

#: The team edition, published separately and installed by licence.
TEAM_DIST_NAME = "edify-agents-teams"

#: The public repository, as `owner/name`.
PUBLIC_REPO = "EDIFY-agents/EDIFY"

#: The public repository's home page.
PUBLIC_URL = "https://github.com/" + PUBLIC_REPO

#: Where a new issue is opened from the command line.
ISSUES_URL = PUBLIC_URL + "/issues/new"

#: The address a licence request goes to.
CONTACT_EMAIL = "santiago92746@gmail.com"

#: Where a person asks for a team or partner licence: an email address and the
#: public issues page.
CONTACT = CONTACT_EMAIL + " or " + PUBLIC_URL + "/issues"

__all__ = [
    "DIST_NAME",
    "TEAM_DIST_NAME",
    "PUBLIC_REPO",
    "PUBLIC_URL",
    "ISSUES_URL",
    "CONTACT_EMAIL",
    "CONTACT",
]
