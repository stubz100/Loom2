"""The orchestrator's routes, one module per domain (D37). `api.create_app` includes `ROUTERS` in this order."""
from . import assets, audio, blobs, clips, documents, engine, events_ws, finals, groups, jobs, meta, models, motion, preset_icons, projects, retouch, settings, stages, story, timelines

ROUTERS = [meta.router, settings.router, projects.router, assets.router, groups.router, documents.router, clips.router, timelines.router,
           stages.router, finals.router, story.router, motion.router, jobs.router, models.router, engine.router, blobs.router, retouch.router, preset_icons.router, audio.router, events_ws.router]
