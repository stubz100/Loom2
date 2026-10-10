"""The orchestrator's live state for one process (06 §1): app settings, the event hub, the roster, the engine supervisor and the
stores of the open project. Routes reach it through `routes/deps.py` (D37).
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import HTTPException

from .catalogue import Catalogue
from .config import AppState
from .documents import DocumentStore
from .engine.supervisor import EngineSupervisor
from .events import EventHub
from .groups import GroupStore
from .queue import JobQueue
from .roster import Roster
from .tools.fetch import FetchJob
from .workspace import Workspace


class Services:
    def __init__(self, state_dir: Path | None = None, variant: str | None = None) -> None:
        self.app = AppState(state_dir, variant)
        self.hub = EventHub()
        self.roster = Roster(self.app.models_root, [Path(p) for p in self.app.settings.mounted_model_trees], self.app.settings.variant)
        self.engine = EngineSupervisor(self.app, on_state=lambda s: self.hub.broadcast("engine.state", s))
        self.ws: Workspace | None = None
        self.catalogue: Catalogue | None = None
        self.queue: JobQueue | None = None
        self.documents: DocumentStore | None = None
        self.groups: GroupStore | None = None
        self.fetches: dict[str, FetchJob] = {}

    # ---- project binding ------------------------------------------------------------------------
    async def open_project(self, path: Path) -> dict:
        await self.close_project()
        ws = await asyncio.to_thread(Workspace.open, path)
        # B8: build everything first so a corrupt catalogue or queue file leaves no half-open project behind.
        # D37: the index open (and a rebuild after a schema change) and the group migration run off the event loop.
        catalogue = await asyncio.to_thread(Catalogue, ws, self.app.settings.thumbnail_sizes, session_id=self.app.session_id)
        try:
            queue = JobQueue(ws, self.app, self.engine, self.roster, catalogue, self.hub)
            documents = DocumentStore(ws)
            queue.documents = documents
            groups = await asyncio.to_thread(GroupStore, ws, catalogue)    # D34: the album pages; migrates collections once
            if groups.migrated:
                catalogue.recovery.append(f"{groups.migrated} collection{'s' if groups.migrated != 1 else ''} became groups on the Album page.")
            await queue.start()
        except Exception:
            catalogue.close()
            raise
        self.ws, self.catalogue, self.queue, self.documents, self.groups = ws, catalogue, queue, documents, groups
        self.app.touch_project(ws.path)
        info = ws.info()
        self.hub.broadcast("project.opened", info)
        return info

    async def close_project(self) -> None:
        if self.queue:
            await self.queue.stop()
            self.queue = None
        if self.catalogue:
            self.catalogue.close()
            self.catalogue = None
        self.documents = None
        self.groups = None
        if self.ws:
            self.hub.broadcast("project.closed", {"path": str(self.ws.path)})
            self.ws = None

    def require_project(self) -> tuple[Workspace, Catalogue, JobQueue]:
        if not (self.ws and self.catalogue and self.queue):
            raise HTTPException(409, "no project is open")
        return self.ws, self.catalogue, self.queue

    def require_groups(self) -> GroupStore:
        self.require_project()
        assert self.groups is not None
        return self.groups

    def require_documents(self) -> DocumentStore:
        self.require_project()
        assert self.documents is not None
        return self.documents

    def group_changed(self, ids) -> None:
        self.hub.broadcast("group.changed", {"ids": sorted(ids)})
