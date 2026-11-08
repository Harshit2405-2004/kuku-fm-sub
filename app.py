"""Streamlit app: upload a screenplay pack (or try the fictional sample), run the pipeline, browse the ranked promos.

Fits on top of promo_finder.pipeline.run_pipeline: this file only collects inputs, shows progress and renders
the run folder's files. Uploads and outputs live in a temp dir per browser session, never in the repo.
An API key typed in the sidebar is passed to each model call through a wrapper in this process only:
it is not put in the environment, the config snapshot, the manifest, the logs or the cache.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv

from promo_finder.config import apply_overrides, load_config
from promo_finder.judge import excerpt
from promo_finder.build import Candidate
from promo_finder.parse import Episode
from promo_finder.pipeline import run_pipeline
from promo_finder.report import segments_text

ROOT = Path(__file__).resolve().parent
SAMPLE = ROOT / "samples" / "synthetic_show"
CONFIG = ROOT / "config.yaml"


def save_uploads(files: list[tuple[str, bytes]], dest: Path) -> Path:
    """Write uploaded (name, bytes) pairs into dest and return the input path for the pipeline.

    One .zip is passed straight through (the parser reads zips); loose .txt files go into a folder.
    Only the base name is used, so a hostile file name can't escape dest.
    """
    dest.mkdir(parents=True, exist_ok=True)
    zips = [f for f in files if f[0].lower().endswith(".zip")]
    if zips:
        path = dest / "pack.zip"
        path.write_bytes(zips[0][1])
        return path
    folder = dest / "pack"
    folder.mkdir(exist_ok=True)
    for name, data in files:
        if name.lower().endswith(".txt"):
            (folder / Path(name).name).write_bytes(data)
    return folder


def key_injecting_completion(api_key: str) -> Callable:
    """litellm.completion with the user's key added to every call (kept out of env, config and cache)."""
    import litellm

    def complete(**kwargs):
        return litellm.completion(**kwargs, api_key=api_key)
    return complete


def build_config(mock: bool, proposer: str, judge: str, api_base: str, use_typed_key: bool, work: Path) -> dict:
    base = load_config(CONFIG)
    default_proposer = base["models"]["proposer"]["model"]
    cfg = apply_overrides(
        base, proposer_model=proposer if proposer and proposer != default_proposer else None,
        # the arc stage follows the proposer if the user swapped it, so one model name is enough in the UI
        arc_model=proposer if proposer and proposer != default_proposer else None,
        judge_model=judge if judge != base["models"]["judge"]["model"] else None,
        api_base=api_base or None, mock=mock)
    if use_typed_key:
        for stage in cfg["models"].values():
            stage["api_key_env"] = None          # the wrapper supplies the key instead
    cfg["cache_dir"] = str(work / "cache")       # session temp dir, not the repo's .cache
    return cfg


def load_results(run_dir: Path) -> list[dict]:
    """Ranked rows for the table, each with its script excerpt, read back from the run folder."""
    ranked = json.loads((run_dir / "ranked.json").read_text(encoding="utf-8"))["ranked"]
    episodes = {e["ep"]: Episode(**e) for e in json.loads((run_dir / "episodes.json").read_text(encoding="utf-8"))}
    rows = []
    for r in ranked:
        cand = Candidate(**{k: r[k] for k in Candidate.model_fields})
        rows.append({
            "rank": r["rank"], "episode": ", ".join(sorted({f"E{s['ep']:02d}" for s in r["segments"]})),
            "segments": segments_text(r["segments"]), "length_s": round(r["total_s"], 1),
            "hook": r["hook_text"], "cliff": r["cliff_text"], "why": r["why"],
            "flags": ", ".join(sorted(set(r["flags"]) | set(r["risk_flags"]))) or "-",
            "excerpt": excerpt(cand, episodes),
        })
    return rows


def run_app_pipeline(input_path: Path, work: Path, cfg: dict, episodes: list[int] | None = None,
                     api_key: str | None = None, progress: Callable[[str, int, int], None] | None = None
                     ) -> tuple[Path, list[dict]]:
    """Run the pipeline in the session's temp dir; return (run folder, result rows). aliases_path=None: no cast file."""
    run_dir = run_pipeline(input_path, cfg, "app", out_root=work / "outputs", aliases_path=None,
                           episodes_filter=episodes, progress=progress,
                           completion_fn=key_injecting_completion(api_key) if api_key else None)
    return run_dir, load_results(run_dir)


def parse_episode_list(text: str) -> list[int] | None:
    """'1, 3, 8' -> [1, 3, 8]; blank -> None (all episodes)."""
    nums = [int(x) for x in text.replace(" ", "").split(",") if x]
    return nums or None


def main() -> None:
    import streamlit as st

    load_dotenv()
    st.set_page_config(page_title="Promo Finder", layout="wide")
    st.title("Promo Finder")
    st.caption("Reads a microdrama screenplay pack and ranks 20–60 s promo clips. "
               "Model-written block IDs become timestamps in code, never the other way round.")
    if "work" not in st.session_state:
        st.session_state.work = tempfile.mkdtemp(prefix="promo_app_")
    work = Path(st.session_state.work)
    base = load_config(CONFIG)

    with st.sidebar:
        st.header("Run settings")
        mock = st.toggle("Mock mode (no API key, canned replies)", value=True)
        proposer = st.text_input("Proposer model", base["models"]["proposer"]["model"], disabled=mock)
        judge = st.text_input("Judge model", base["models"]["judge"]["model"], disabled=mock)
        api_base = st.text_input("API base (optional, OpenAI-compatible)", "", disabled=mock)
        api_key = st.text_input("API key (optional)", type="password", disabled=mock,
                                help="Used only in this process for this run. Not saved anywhere. "
                                     "One key is used for every stage; leave blank to use server environment variables.")
        episodes_text = st.text_input("Episodes to run (blank = all)", "", help="e.g. 1,3,8. Real runs cost tokens.")

    st.subheader("1. Input")
    uploads = st.file_uploader("Upload a .zip or several episode .txt files", type=["zip", "txt"],
                               accept_multiple_files=True)
    use_sample = st.button("Try the fictional sample (3 episodes)")
    if use_sample:
        st.session_state.source = "sample"
    elif uploads:
        st.session_state.source = "upload"
    source = st.session_state.get("source")
    st.write({"sample": "Using the fictional sample show.", "upload": f"Using {len(uploads or [])} uploaded file(s)."}
             .get(source, "Pick an input above."))

    if st.button("Run", type="primary", disabled=source is None):
        try:
            episodes = parse_episode_list(episodes_text)
        except ValueError:
            st.error("Episodes must be numbers separated by commas, like 1,3,8.")
            st.stop()
        if source == "sample":
            input_path = SAMPLE
        else:
            input_path = save_uploads([(f.name, f.getvalue()) for f in uploads], work / "upload")
        cfg = build_config(mock, proposer, judge, api_base, bool(api_key) and not mock, work)
        bars = {"propose": st.progress(0.0, "Proposing clips per episode"), "judge": st.progress(0.0, "Judging")}

        def progress(stage: str, done: int, total: int) -> None:
            if stage in bars:
                bars[stage].progress(done / max(total, 1), f"{stage}: {done}/{total}")

        with st.spinner("Running the pipeline..."):
            try:
                run_dir, rows = run_app_pipeline(input_path, work, cfg, episodes, api_key or None, progress)
            except Exception as error:                   # show the reason instead of a stack trace
                st.error(f"Run failed: {type(error).__name__}: {str(error)[:300]}")
                st.stop()
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        st.session_state.result = {
            "rows": rows, "promos_csv": (run_dir / "promos.csv").read_bytes(),
            "review_md": (run_dir / "review.md").read_bytes(), "errors": manifest["errors"],
            "counts": manifest["counts"], "mock": manifest["mock"]}

    result = st.session_state.get("result")
    if result:
        st.subheader("2. Ranked promos")
        c = result["counts"]
        st.write(f"Built {c['built']} clips, ranked {c['ranked']}, unscored {c['unscored']}, "
                 f"{len(result['errors'])} error(s)." + (" Mock mode: the replies are canned, so the picks only show the format." if result["mock"] else ""))
        if result["errors"]:
            with st.expander("Errors"):
                st.json(result["errors"][:10])
        if not result["rows"]:
            st.warning("No ranked clips. Check the errors above (a missing or wrong API key is the usual cause).")
        else:
            table = [{k: v for k, v in r.items() if k != "excerpt"} for r in result["rows"]]
            st.dataframe(table, width="stretch", hide_index=True)
            for r in result["rows"]:
                with st.expander(f"#{r['rank']} {r['segments']}: script excerpt"):
                    st.code(r["excerpt"], language=None)
        left, right = st.columns(2)
        left.download_button("Download promos.csv", result["promos_csv"], "promos.csv", "text/csv")
        right.download_button("Download review.md", result["review_md"], "review.md", "text/markdown")


if __name__ == "__main__":
    main()
