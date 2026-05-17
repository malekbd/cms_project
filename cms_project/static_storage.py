from django.contrib.staticfiles.storage import ManifestStaticFilesStorage


class NonStrictManifestStaticFilesStorage(ManifestStaticFilesStorage):
    """Fall back to plain static paths if collectstatic's manifest is stale."""

    manifest_strict = False
