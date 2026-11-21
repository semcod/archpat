"""Architecture synthesis, with explicit evidence and bounded search."""
from .models import ArchitectureGraph, StorySpec, SynthesisResult
from .synthesis import synthesize
from .validation import validate_graph

__version__ = "0.1.0"
__all__ = ["ArchitectureGraph", "StorySpec", "SynthesisResult", "synthesize", "validate_graph"]

