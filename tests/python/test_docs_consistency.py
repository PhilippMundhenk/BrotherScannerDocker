"""The README documents every setting the catalogue offers, and the catalogue knows every setting the README lists.

The settings catalogue (www/private/settings-catalogue.php) drives the settings page and the
configuration file; the README options table is what users read. The two drift apart easily,
so this test keeps them in step (#128).
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# settings the README documents outside the options table or that are not user settings
# WEBSERVER and SCANNER_CONFIG_FILE are read by the entrypoint only and cannot come from the file
README_ONLY = {"UID", "GID", "WEBSERVER", "SCANNER_CONFIG_FILE", "FTP_PASSWORD_FILE", "SSH_PASSWORD_FILE", "TELEGRAM_TOKEN_FILE",
               "FTP_USER_FILE", "SSH_USER_FILE", "TELEGRAM_CHATID_FILE"}


def catalogue_keys():
    text = (ROOT / "www" / "private" / "settings-catalogue.php").read_text(encoding="utf-8")
    return set(re.findall(r"'key'\s*=>\s*'([A-Z][A-Z0-9_]*)'", text))


def readme_table_keys():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    keys = set()
    for line in text.splitlines():
        if not line.startswith("| ") or line.startswith("| Variable") or line.startswith("| ---"):
            continue
        first = line.split("|")[1]
        keys.update(re.findall(r"\b([A-Z][A-Z0-9_]+)\b", first))
    return keys


def test_every_catalogue_setting_is_in_the_readme_table():
    missing = catalogue_keys() - readme_table_keys()
    assert not missing, f"settings in the catalogue but not in the README options table: {sorted(missing)}"


def test_every_readme_setting_is_in_the_catalogue():
    unknown = readme_table_keys() - catalogue_keys() - README_ONLY
    assert not unknown, f"settings in the README options table but not in the catalogue: {sorted(unknown)}"


def test_swagger_lists_every_api_route():
    """Every /api route in index.php has a path in doc/swagger.yaml."""
    index = (ROOT / "www" / "html" / "index.php").read_text(encoding="utf-8")
    swagger = (ROOT / "doc" / "swagger.yaml").read_text(encoding="utf-8")
    routes = set(re.findall(r"\$router->map\(\s*'[A-Z]+',\s*'/api(/[^']*)'", index))
    documented = set(re.findall(r"^  (/[^\s:]+):", swagger, re.M))

    def normalise(route):
        return re.sub(r"\[char:(\w+)\]", r"{\1}", route).replace("{parameter}", "{target}").replace("{job_id}", "{id}")

    missing = {r for r in routes if normalise(r) not in documented and not r.startswith("/dev/")}
    assert not missing, f"API routes without a swagger entry: {sorted(missing)}"
