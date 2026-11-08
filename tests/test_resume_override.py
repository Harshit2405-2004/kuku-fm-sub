"""Per-episode proposer override (mid-run host switch) and the arc_ rejection-reason prefix."""
from pathlib import Path

from promo_finder.config import load_config
from promo_finder.pipeline import _proposer_cfg_for, run_pipeline
from run import parse_episode_proposers


def test_parse_episode_proposers_ranges_and_lists():
    got = parse_episode_proposers(["3,17-19=groq/x"], {})
    assert sorted(got) == [3, 17, 18, 19] and got[18] == {"model": "groq/x"}


def test_parse_episode_proposers_key_env_suffix():
    got = parse_episode_proposers(["5-6=gemini/x|GEMINI_API_KEY"], {})
    assert got[5] == {"model": "gemini/x", "api_key_env": "GEMINI_API_KEY"} and got[6] == got[5]


def test_override_only_touches_listed_episodes():
    cfg = load_config("config.yaml")
    cfg["episode_proposers"] = {3: {"model": "groq/other"}}
    assert _proposer_cfg_for(cfg, 3)["models"]["proposer"]["model"] == "groq/other"
    assert _proposer_cfg_for(cfg, 4) is cfg
    assert cfg["models"]["proposer"]["model"] != "groq/other"   # original untouched


def test_mock_run_reuses_dir_and_records_model_per_episode(tmp_path: Path):
    cfg = load_config("config.yaml")
    cfg["mock"] = True
    d = tmp_path / "myrun"
    out = run_pipeline("samples/synthetic_show", cfg, "x", aliases_path="config/aliases.example.yaml",
                       reuse_dir=d)
    assert out == d
    import json
    m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    assert m["proposer_model_by_episode"] and all(v == "mock" or "/" in v for v in m["proposer_model_by_episode"].values())


def test_arc_rejection_reason_keeps_prefix(tmp_path: Path):
    import json
    cfg = load_config("config.yaml")
    cfg["mock"] = True
    cfg["arcs"] = {"enabled": True}
    out = run_pipeline("samples/synthetic_show", cfg, "arcx", out_root=tmp_path, aliases_path="config/aliases.example.yaml")
    rej = json.loads((out / "rejected.json").read_text(encoding="utf-8"))["rejected"]
    arc = [r for r in rej if str(r.get("reason", "")).startswith("arc_") or r.get("candidate_ids") or r.get("opener")]
    for r in rej:
        if "opener" in r or "closer" in r:
            assert r["reason"].startswith("arc_")
