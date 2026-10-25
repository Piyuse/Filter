class UserInputError(ValueError):
    """A curated, safe-to-display validation message (never a parser exception)."""


class DetectionUnavailableError(RuntimeError):
    """The required local privacy engine cannot safely process a request."""
