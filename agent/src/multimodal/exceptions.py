"""Exceptions for multimodal adapter."""

from __future__ import annotations


class MultimodalError(Exception):
    """Base exception for multimodal adapter errors."""


class InputValidationError(MultimodalError):
    """Raised when input data fails validation."""


class URLSecurityError(MultimodalError):
    """Raised when a URL fails security checks."""


class URLFetchError(MultimodalError):
    """Raised when a URL cannot be fetched."""


class VisionProviderError(MultimodalError):
    """Raised when a vision provider fails to analyze an image."""


class ImageProcessingError(MultimodalError):
    """Raised when image processing fails."""