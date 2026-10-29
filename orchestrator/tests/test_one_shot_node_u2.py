"""U2 (G5, D157 Q3): one Shot node type — a Dialogue is a Shot with lines. A node file or a client naming `dialogue` reads as `shot`; what
"a Dialogue node" meant (voicing, the speakers, a final's lines) is "a Shot with lines" now; the type is no longer offered."""
from pathlib import Path

from loom2.fsio import atomic_write_json
from loom2.story import NODE_TYPES, VISUAL_TYPES, FlowNode, ShotTemplate, StoryStore, has_lines, node_type
from loom2.workspace import Workspace


def test_dialogue_reads_as_a_shot_with_its_lines(tmp_path: Path):
    ws = Workspace.create(tmp_path / "p", name="P")
    st = StoryStore(ws)
    made = st.create_node("dialogue", "Talk", lines=[{"speaker": None, "text": "Not now."}])     # an old client's type
    assert made.type == "shot" and made.shot_id and made.lines[0].text == "Not now."
    (ws.story_dir / "flow" / "nodes").mkdir(parents=True, exist_ok=True)
    atomic_write_json(ws.story_dir / "flow" / "nodes" / "node_old.json", {"schema_version": 2, "id": "node_old", "type": "dialogue", "title": "Before D157",
                                                                          "lines": [{"speaker": None, "text": "Hello."}]})
    old = FlowNode.model_validate({"id": "node_x", "type": "dialogue", "title": "x"})
    assert old.type == "shot" and ShotTemplate(name="t", node_type="dialogue").node_type == "shot"
    assert "dialogue" not in NODE_TYPES and VISUAL_TYPES == ("shot",) and node_type("dialogue") == "shot" and node_type("choice") == "choice"


def test_a_shot_with_lines_is_what_a_dialogue_was():
    talk = FlowNode(type="shot", lines=[{"speaker": "prf_m", "text": "Hi."}])
    quiet = FlowNode(type="shot", text="the ferry leaves")
    blank = FlowNode(type="shot", lines=[{"speaker": None, "text": "  "}])
    choice = FlowNode(type="choice", lines=[{"speaker": None, "text": "x"}])
    assert [has_lines(n) for n in (talk, quiet, blank, choice, None)] == [True, False, False, False, False]
