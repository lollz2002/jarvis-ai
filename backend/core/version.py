"""
Albert OS — Version
Spek: 49_RELEASE_AND_VERSIONING_BIBLE.md

Semver: MAJOR.MINOR.PATCH
Release types: alpha, beta, rc, stable, hotfix
"""

MAJOR   = 1
MINOR   = 0
PATCH   = 0
RELEASE = "alpha"   # alpha | beta | rc | stable | hotfix

VERSION = f"{MAJOR}.{MINOR}.{PATCH}-{RELEASE}"
VERSION_TUPLE = (MAJOR, MINOR, PATCH)


def version_info() -> dict:
    return {
        "version":       VERSION,
        "major":         MAJOR,
        "minor":         MINOR,
        "patch":         PATCH,
        "release_type":  RELEASE,
        "api_version":   "v1",
        "plugin_sdk":    "2.0.0",
    }
