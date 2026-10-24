"""D127 (proto01_animate 30 §16, AU3): the installed VST3 effects loom2's own host can run — the system's VST3 folders and the author's
(Settings › vsthost › folders), each bundle scanned once by the sidecar (loom2/vsthost.py) and kept until it changes."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from ..vsthost import VstHostError
from .deps import Svc

router = APIRouter(tags=["audio"])


class VstPlugin(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    bundle: str                                    # the .vst3 bundle's path
    uid: str                                       # the effect's class id in it
    name: str
    vendor: str = ""
    version: str = ""
    sub: str = ""                                  # its sub-categories ("Fx|Reverb")


class VstFailed(BaseModel):
    bundle: str
    error: str


class VstPluginList(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    available: bool                                # loom2's host is built here
    plugins: list[VstPlugin] = Field(default_factory=list)
    failed: list[VstFailed] = Field(default_factory=list)
    error: str | None = None                       # why there is no list (the host is not built, or refused)


@router.get("/audio/plugins", response_model=VstPluginList)
async def audio_plugins(svc: Svc, rescan: bool = False):
    """The installed effects (instruments left out), scanned in a process per bundle; `rescan` scans every bundle again."""
    host = svc.vsthost
    if not host.available():
        return {"available": False, "error": "loom2's VST3 host is not built here (python scripts/build_vsthost.py)"}
    try:
        return {"available": True, **await asyncio.to_thread(host.plugins, rescan)}
    except VstHostError as e:
        return {"available": True, "error": str(e)}
