"""D66 (ArtCraft P4): where a job came from — echoed on the job, its events and the assets it makes, so every surface can route a result
back (Generate's batch, Animate's clip view, the Edit document, a Catalogue page) and the Dock can offer "Go to origin"."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class JobOrigin(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)   # D38: present in every reply → required in the schema
    suite: Literal["generate", "edit", "animate", "catalogue", "api"]
    surface: str                                   # results · ref-slot · clip · ai · group … — the panel or view that asked
    ref: str | None = None                         # what it was about: a document, clip, group or batch id
    payload: dict[str, Any] | None = None          # anything the surface needs to show the result in place (a slot number, a view)
