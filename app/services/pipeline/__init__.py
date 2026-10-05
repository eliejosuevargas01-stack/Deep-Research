"""Pipeline internals: scout, worker, audit, writer stages extracted from research.py.

Import stages via their submodules directly:
    from app.services.pipeline.scout import scout
    from app.services.pipeline.worker import run_worker

ponytail: do NOT re-export `scout` here — the name collides with the
app.services.pipeline.scout submodule and breaks monkeypatch path resolution.
"""
