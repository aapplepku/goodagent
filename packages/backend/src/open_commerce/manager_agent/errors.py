"""Safe manager-agent application errors."""


class ManagerThreadNotFoundError(ValueError):
    """The tenant-scoped manager thread does not exist."""


class ManagerThreadBusyError(RuntimeError):
    """The conversation advanced while an agent response was being prepared."""


class ManagerThreadInvalidError(ValueError):
    """A channel or reply-thread operation violates the workspace contract."""


class ManagerMemoryNotFoundError(ValueError):
    """The tenant-scoped manager memory does not exist."""


class ManagerMemoryImmutableError(ValueError):
    """A working or periodic memory cannot be manually deleted."""


class ManagerModelUnavailableError(RuntimeError):
    """The configured conversation model failed safely without fallback."""


class ManagerDatasetProfileError(ValueError):
    """A manager-provided dataset failed bounded structural validation."""
