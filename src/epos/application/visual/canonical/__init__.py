"""Module 12 visual canonicalization boundary for EPOS NEXT."""

from epos.application.visual.canonical.canonicalizer import VisualCanonicalizer
from epos.application.visual.canonical.errors import (
    SemanticLibraryResolutionError,
    VisualCanonicalizationError,
)
from epos.application.visual.canonical.library import (
    SemanticLibraryResolver,
    SemanticResolverProtocol,
)
from epos.application.visual.canonical.models import (
    CanonicalAction,
    CanonicalCamera,
    CanonicalLocation,
    CanonicalSubject,
    CanonicalVST,
    CanonicalVisualFocus,
    CanonicalVisualIdentity,
    ResolvedLora,
    ResolvedSemanticEntry,
)

__all__ = [
    "CanonicalAction",
    "CanonicalCamera",
    "CanonicalLocation",
    "CanonicalSubject",
    "CanonicalVST",
    "CanonicalVisualFocus",
    "CanonicalVisualIdentity",
    "ResolvedLora",
    "ResolvedSemanticEntry",
    "SemanticLibraryResolutionError",
    "SemanticLibraryResolver",
    "SemanticResolverProtocol",
    "VisualCanonicalizationError",
    "VisualCanonicalizer",
]
