"""Optional local REST facade. No runtime execution or arbitrary file access."""
from __future__ import annotations
from .models import ArchitectureGraph, StorySpec, SynthesisResult
from .operations import validate_operation
from .synthesis import synthesize


def create_app():
    try:
        from fastapi import FastAPI
    except ImportError as exc:
        raise RuntimeError('Install archpat[api] to use the REST facade') from exc
    app = FastAPI(title="ArchPat", version="0.1.0", description="Architecture proposals; execution_ready is always false.")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "version": "0.1.0"}

    @app.post("/v1/synthesize", response_model=SynthesisResult)
    def plan(story: StorySpec) -> SynthesisResult:
        return synthesize(story)

    @app.post("/v1/validate")
    def validate(graph: ArchitectureGraph) -> dict:
        return validate_operation(graph.model_dump(mode="json"))

    return app

