"""app.py imports without starting the UI, saves uploads safely, keeps the typed key out of config and cache,
and a mock run on the fictional sample returns ranked rows. No network."""

import json
import zipfile
from pathlib import Path

import app

SYNTH = Path(__file__).resolve().parent.parent / "samples" / "synthetic_show"


def test_mock_run_on_sample_returns_ranked_rows(tmp_path):
    cfg = app.build_config(True, "", "", "", False, tmp_path)
    run_dir, rows = app.run_app_pipeline(SYNTH, tmp_path, cfg)
    assert rows and [r["rank"] for r in rows] == list(range(1, len(rows) + 1))
    assert all(r["segments"] and r["hook"] and r["excerpt"] for r in rows)
    assert (run_dir / "promos.csv").exists() and (run_dir / "review.md").exists()
    assert str(tmp_path) in str(run_dir)           # outputs stay in the session temp dir


def test_loose_txt_uploads_are_flattened_and_non_txt_ignored(tmp_path):
    path = app.save_uploads([("../../evil.txt", b"x"), ("notes.pdf", b"y")], tmp_path / "up")
    assert [p.name for p in path.iterdir()] == ["evil.txt"]
    assert path.parent == tmp_path / "up"


def test_zip_upload_is_passed_through(tmp_path):
    z = tmp_path / "a.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("episode-001.txt", "hi")
    path = app.save_uploads([("a.zip", z.read_bytes())], tmp_path / "up")
    assert path.suffix == ".zip"


def test_typed_key_never_reaches_config_or_manifest(tmp_path):
    secret = "sk-test-SECRET-123"
    cfg = app.build_config(False, "", "", "", True, tmp_path)
    assert all(s["api_key_env"] is None for s in cfg["models"].values())
    assert secret not in json.dumps(cfg)
    seen = {}

    import litellm
    orig = litellm.completion
    litellm.completion = lambda **kw: seen.update(kw) or (_ for _ in ()).throw(RuntimeError("stop"))
    try:
        try:
            app.key_injecting_completion(secret)(model="m", messages=[])
        except RuntimeError:
            pass
    finally:
        litellm.completion = orig
    assert seen["api_key"] == secret               # the wrapper does supply it to the call


def test_episode_list_parsing():
    assert app.parse_episode_list("1, 3,8") == [1, 3, 8]
    assert app.parse_episode_list("") is None


def test_proposer_prompt_is_selectable_and_version_recorded(tmp_path):
    names = app.proposer_prompts()
    assert names["proposer"] == "proposer_v3" and names["proposer_v4"] == "proposer_v4"
    cfg = app.build_config(True, "", "", "", False, tmp_path, "proposer_v4")
    assert cfg["prompts"]["proposer"] == "proposer_v4"
    run_dir, _ = app.run_app_pipeline(SYNTH, tmp_path, cfg)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["prompt_versions"]["proposer"] == "proposer_v4"
    default = app.build_config(True, "", "", "", False, tmp_path)
    assert default["prompts"]["proposer"] == "proposer"          # default file is v3


def test_prompt_version_changes_the_cache_key():
    from promo_finder.cache import cache_key
    msgs = [{"role": "user", "content": "x"}]
    assert cache_key("m", "proposer_v3", msgs, "S", None) != cache_key("m", "proposer_v4", msgs, "S", None)
