"""Config + CLI-override tests (TECH_SPEC §5): the model-swap path Kuku will use in the interview."""

from pathlib import Path

from promo_finder.config import apply_overrides, load_config

CONFIG = Path(__file__).resolve().parent.parent / "config.yaml"


def test_load_config_has_three_stages():
    cfg = load_config(CONFIG)
    assert set(cfg["models"]) >= {"proposer", "arc", "judge"}
    for stage in cfg["models"].values():
        assert stage["temperature"] == 0


def test_model_flag_swaps_every_stage_with_api_base():
    cfg = apply_overrides(load_config(CONFIG), model="openai/their-model",
                          api_base="https://example.test/v1", api_key_env="KUKU_API_KEY")
    for stage in ("proposer", "arc", "judge"):
        assert cfg["models"][stage]["model"] == "openai/their-model"
        assert cfg["models"][stage]["api_base"] == "https://example.test/v1"
        assert cfg["models"][stage]["api_key_env"] == "KUKU_API_KEY"


def test_judge_only_swap_leaves_other_stages_alone():
    base = load_config(CONFIG)
    cfg = apply_overrides(base, judge_model="openai/their-model",
                          api_base="https://example.test/v1", api_key_env="KUKU_API_KEY")
    assert cfg["models"]["judge"]["model"] == "openai/their-model"
    assert cfg["models"]["judge"]["api_base"] == "https://example.test/v1"
    assert cfg["models"]["proposer"] == base["models"]["proposer"]
    assert cfg["models"]["proposer"]["api_base"] is None


def test_stage_flag_beats_global_model_flag():
    cfg = apply_overrides(load_config(CONFIG), model="openai/a", proposer_model="openai/b")
    assert cfg["models"]["proposer"]["model"] == "openai/b"
    assert cfg["models"]["judge"]["model"] == "openai/a"


def test_api_base_alone_applies_to_all_stages():
    cfg = apply_overrides(load_config(CONFIG), api_base="http://localhost:8000/v1")
    assert all(s["api_base"] == "http://localhost:8000/v1" for s in cfg["models"].values())


def test_overrides_do_not_mutate_the_input():
    base = load_config(CONFIG)
    before = base["models"]["judge"]["model"]
    apply_overrides(base, model="openai/x")
    assert base["models"]["judge"]["model"] == before


def test_flags_for_mock_and_no_cache():
    cfg = apply_overrides(load_config(CONFIG), mock=True, no_cache=True)
    assert cfg["mock"] is True and cfg["no_cache"] is True
