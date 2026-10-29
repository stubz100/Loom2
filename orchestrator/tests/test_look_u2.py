"""U2 (D157, G2): the Look is the project's record — its styles, the default and the sample scene the styles' samples are rendered on (F3:
a harbour story's styles were judged on "a cyber spy in an office", the app-wide scene). A world written before keeps the app's scene."""
from pathlib import Path

from loom2.fsio import atomic_write_json
from loom2.story import StoryStore
from loom2.workspace import Workspace


def test_the_project_keeps_its_sample_scene(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P")
    st = StoryStore(ws)
    w = st.put_world({"revision": 0, "sample_scene": "a fishing harbour at dusk, a ferry at the pier"})
    assert StoryStore(ws).world().sample_scene == "a fishing harbour at dusk, a ferry at the pier" and w.revision == 1
    atomic_write_json(ws.story_dir / "world.json", {"schema_version": 1, "logline": "", "synopsis": "", "styles": [], "revision": 3})
    assert StoryStore(ws).world().sample_scene == ""                                 # before U2: Settings › Samples' scene
