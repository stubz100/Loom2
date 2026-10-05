from pathlib import Path

import pytest

from loom2.engine import contract
from loom2.roster import ROSTER, ROSTER_BY_ID, Roster


def test_roster_catalogue_is_consistent():
    assert len({e.id for e in ROSTER}) == len(ROSTER)
    assert len({(e.folder, e.name) for e in ROSTER}) == len(ROSTER)
    for e in ROSTER:
        assert e.variants and set(e.variants) <= {"full", "open"}
        if "open" in e.variants:
            assert "nc" not in e.license.lower(), f"{e.id} is in the open variant with a non-commercial licence"


def test_roster_scan_resolve(models_tree: Path):
    r = Roster(models_tree, variant="full").scan()
    dev = r.resolve("flux2-dev-fp8mixed")
    assert dev.health == "present" and dev.path and dev.size == 16
    vae = r.resolve("flux2-vae")
    assert vae.health == "verified" and vae.sha256 == "ab" * 32          # ledger size matches
    assert r.resolve("klein-9b").health == "missing"
    assert r.resolve("flux1-fill-dev").health == "retired"
    assert r.require("flux2-dev-fp8mixed") == ("diffusion_models", "flux2_dev_fp8mixed.safetensors")
    with pytest.raises(FileNotFoundError):
        r.require("klein-9b")
    with pytest.raises(KeyError):
        r.resolve("nope")
    stray = [u["name"] for u in r.unlisted_files()]
    assert stray == ["stray-model.safetensors"]
    listing = r.listing()
    assert all(x["retired"] is None for x in listing)
    open_only = Roster(models_tree, variant="open").scan().listing()
    assert all("open" in x["variants"] for x in open_only) and len(open_only) < len(listing)


def test_contract_check_and_name_resolution(object_info: dict):
    g = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "flux2_dev_fp8mixed.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "mistral_3_small_flux2_fp8.safetensors", "type": "flux2", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae.safetensors"}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": "a cat", "clip": ["2", 0]}},
        "8": {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": 960, "height": 544, "batch_size": 1}},
        "9": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "seed": 1, "steps": 4, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple",
                                                  "positive": ["5", 0], "negative": ["5", 0], "latent_image": ["8", 0], "denoise": 1.0}},
        "10": {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["3", 0]}},
        "11": {"class_type": "SaveImage", "inputs": {"images": ["10", 0], "filename_prefix": "t"}},
    }
    assert contract.check_graph(object_info, g) == []
    bad = {
        "1": {"class_type": "NoSuchNode", "inputs": {}},
        "9": {"class_type": "KSampler", "inputs": {"model": ["7", 0], "seed": "x", "sampler_name": "not-a-sampler"}},
    }
    problems = contract.check_graph(object_info, bad)
    text = "\n".join(problems)
    assert "unknown node class" in text and "links to missing node" in text and "expects INT" in text and "not in enum" in text
    assert "required 'steps' missing" in text
    # sub-folder names: the engine lists 't5\\t5xxl…' for a mounted sub-folder; we pass the basename
    g2 = {"2": {"class_type": "DualCLIPLoader", "inputs": {"clip_name1": "clip_l.safetensors", "clip_name2": "t5xxl_fp8_e4m3fn_scaled.safetensors", "type": "flux"}}}
    notes = contract.resolve_names(object_info, g2)
    assert any("clip_name2" in n for n in notes) or contract.check_graph(object_info, g2) == []


def test_node_signature(object_info: dict):
    s = contract.node_signature(object_info, "KSampler")
    assert s.startswith("KSampler") and "steps:INT" in s
    assert contract.node_signature(object_info, "Nope").endswith("<unknown>")
