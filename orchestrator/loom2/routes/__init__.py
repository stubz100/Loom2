"""The orchestrator's routes, one module per domain (D37). `api.create_app` includes `ROUTERS` in this order."""
from . import assets, blobs, clips, documents, engine, events_ws, groups, jobs, meta, models, projects, retouch, settings

ROUTERS = [meta.router, settings.router, projects.router, assets.router, groups.router, documents.router, clips.router,
           jobs.router, models.router, engine.router, blobs.router, retouch.router, events_ws.router]
