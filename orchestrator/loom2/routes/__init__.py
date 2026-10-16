"""The orchestrator's routes, one module per domain (D37). `api.create_app` includes `ROUTERS` in this order."""
from . import assets, blobs, clips, documents, engine, events_ws, groups, jobs, meta, models, preset_icons, projects, retouch, settings, stages, story, timelines

ROUTERS = [meta.router, settings.router, projects.router, assets.router, groups.router, documents.router, clips.router, timelines.router,
           stages.router, story.router, jobs.router, models.router, engine.router, blobs.router, retouch.router, preset_icons.router, events_ws.router]
