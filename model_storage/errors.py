class StorageError(Exception):
    """Base error for model storage workflow."""


class CompressionError(StorageError):
    """Raised when Draco compression fails."""


class UploadError(StorageError):
    """Raised when cloud upload fails."""


class DatabaseError(StorageError):
    """Raised when database operations fail."""
