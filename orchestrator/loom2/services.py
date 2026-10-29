"""The orchestrator's live state for one process (06 §1): app settings, the event hub, the roster, the engine supervisor and the
stores of the open project. Routes reach it through `routes/deps.py` (D37).
"""
from __future__ import annotations

import logging

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
from .effectcraft import EffectCraft
from .filmcraft import FilmCraft
from .vsthost import VstHost
from .workspace import Workspace


log = logging.getLogger(__name__)


class Services:
    def __init__(self, state_dir: Path | None = None, variant: str | None = None) -> None:
        self.app = AppState(state_dir, variant)
        self.hub = EventHub()
        self.roster = Roster(self.app.models_root, [Path(p) for p in self.app.settings.mounted_model_trees], self.app.settings.variant)
        self.engine = EngineSupervisor(self.app, on_state=lambda s: self.hub.broadcast("engine.state", s))
        self.effectcraft = EffectCraft(self.app)                            # AE1 (D114): the animation editor's engine, started on first use
        self.filmcraft = FilmCraft(self.app)                                # CE1 (D126): the cut editor's engine, started on first use
        self.vsthost = VstHost(self.app)                                    # D127 (AU3): loom2's own VST3 host, one process per request
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
            queue.groups = groups                                           # D73: @mentions resolve against them
            queue.filmcraft = self.filmcraft                                # CE1 (D126): the movie conforms a FilmCraft cut's takes through the session
            queue.vsthost = self.vsthost                                    # AU4 (D127): the movie prints a track's effects first
            if groups.migrated:
                catalogue.recovery.append(f"{groups.migrated} collection{'s' if groups.migrated != 1 else ''} became groups on the Album page.")
            from .story import StoryStore
            catalogue.recovery.extend((await asyncio.to_thread(StoryStore, ws)).migrated)   # RC2a: the shots join their nodes, once
            from .bins import migrate_bins
            catalogue.recovery.extend(await asyncio.to_thread(migrate_bins, ws, groups))     # U2 (G1): the pages into their homes, once
            await queue.start()
        except Exception:
            catalogue.close()
            raise
        self.ws, self.catalogue, self.queue, self.documents, self.groups = ws, catalogue, queue, documents, groups
        self.app.touch_project(ws.path)
        info = ws.info()
        self.hub.broadcast("project.opened", info)
        return info

    def publish_trained(self) -> None:
        """V2: the open project's trained LoRAs mounted for the engine and known to the roster's `trained` map (LT2) — after every roster
        scan, not only at the queue's start (a settings change used to leave them unknown, 422 on submit and gone from /capabilities,
        until the project was reopened). Thread work; never raises."""
        if self.ws is None:
            return
        from .loras import LoraRegistry, publish
        try:
            publish(self.roster, LoraRegistry(self.ws), Path(self.app.settings.models_root), (self.ws.info() or {}).get("id") or self.ws.path.name)
        except Exception as e:  # noqa: BLE001 — a torn registry never blocks a settings change
            log.warning("trained LoRAs not published: %s", e)

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
