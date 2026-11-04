"""C4 (D181, propo02 04 §4.4; findings P13, P25): the storyboard's order is the route, and no bare stage is left behind.

- P25: a Flow made from the storyboard (＋ New shot, nothing before it) gets a Start node wired to its first shot, so the route Episode
  walks begins there; the next shots chain after the one before; a Flow that has a Start gets no second one;
- P13: *A new scene at a World place* on a shot whose scene was the bare stage *New shot* made deletes that bare stage once nothing looks
  through it; a stage with something on it, or one another shot uses, stays.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loom2.catalogue import Catalogue  # noqa: E402
from loom2.groups import GroupStore  # noqa: E402
from loom2.stages import StageObject, StageStore  # noqa: E402
from loom2.story import StoryStore  # noqa: E402
from loom2.workspace import Workspace  # noqa: E402


def test_the_storyboards_order_is_the_route(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P")
    st = StoryStore(ws)
    a = st.make_shot("Wide")                                                   # the first card: nothing before it
    g = st.flow_graph()
    starts = [r for r in st.flow_nodes().values() if r.type == "start"]
    assert len(starts) == 1 and g.start == starts[0].id
    assert any(e.from_ == starts[0].id and e.to == a.id for e in g.edges)     # Start → the first shot
    b = st.make_shot("Close", after=a.id)
    g = st.flow_graph()
    assert any(e.from_ == a.id and e.to == b.id for e in g.edges)             # chained after the one before
    assert len([r for r in st.flow_nodes().values() if r.type == "start"]) == 1          # no second Start
    c = st.make_shot("Insert", after=b.id, at=(900.0, 40.0), connect=False)    # W30: unwired on the canvas — no Start made for it either
    assert not any(e.to == c.id for e in st.flow_graph().edges) and len([r for r in st.flow_nodes().values() if r.type == "start"]) == 1


def test_no_bare_stage_is_left_behind(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P")
    st, stages = StoryStore(ws), StageStore(ws)
    quay = st.create_profile("Quay", "place", GroupStore(ws, Catalogue(ws, [32])))
    n = st.make_shot("Wide")                                                   # a bare stage of its own
    bare = st.shot(n.shot_id).version().stage_id
    assert stages.get(bare) is not None and not stages.get(bare).objects
    s = st.rescene(n.shot_id, "v1", "new", place_id=quay.id)                   # the header's "A new scene at a World place"
    assert s.version().stage_id != bare
    assert stages.get(bare) is None                                            # P13: the bare stage went with the move
    # a stage with something on it stays
    used = s.version().stage_id
    doc = stages.get(used)
    stages.put(used, {"revision": doc.revision, "objects": [StageObject(id="o1", kind="mannequin", name="Figure").model_dump()]})
    s2 = st.rescene(n.shot_id, "v1", "new")
    assert s2.version().stage_id != used and stages.get(used) is not None
    # a bare stage another shot looks through stays
    m = st.make_shot("Two", after=n.id)
    shared = st.shot(m.shot_id).version().stage_id
    st.set_source(s2.id, "v1", shared, stages.get(shared).cameras[0].id, stages.get(shared).revision)
    assert st.shot(s2.id).version().stage_id == shared                        # the first shot looks through the second's stage too
    s3 = st.rescene(m.shot_id, "v1", "new")
    assert s3.version().stage_id != shared and stages.get(shared) is not None   # still used: it stays
