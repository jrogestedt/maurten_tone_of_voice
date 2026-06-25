"""Golden-set evaluation for the tone-of-voice review path.

Runs the LIVE review path (real Opus calls) against curated copy samples and
asserts score ranges and expected / forbidden flags. This is how we *ensure*
accuracy rather than assume it: run it after any change to the persona, the
reference documents, the model, or the prompt / caching code, and to compare
configurations (e.g. adaptive thinking on vs off, Opus vs Sonnet).

Cost: each sample is one review call. The first call in a run writes the
system-prompt cache (~$0.10-0.20); the rest are cache reads (~$0.03). A full
10-sample run is well under $1.

Usage (from the backend/ directory):
    ANTHROPIC_API_KEY=... .venv/bin/python -m eval.run_eval
    ANTHROPIC_API_KEY=... .venv/bin/python -m eval.run_eval --only emoji

Exit code is 0 only if every sample passes (CI-friendly).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml
from sqlmodel import Session, SQLModel, create_engine

from app.anthropic_client import run_review
from app.config import get_settings
from app.seed import seed
from app.voice import build_review_prompt, build_system_prompt

GOLDEN = Path(__file__).resolve().parent / "golden_set.yaml"


def _notes_text(result: dict) -> str:
    """All reviewer prose flattened, lowercased, for substring assertions."""
    parts = [result.get("verdict", "")]
    for n in result.get("notes", []):
        parts += [n.get("type", ""), n.get("flag", ""), n.get("quote", ""), n.get("issue", ""), n.get("fix", "")]
    return " \n ".join(parts).lower()


def _evaluate(sample: dict, result: dict) -> list[str]:
    fails: list[str] = []
    exp = sample.get("expect", {})
    score = result.get("score")
    text = _notes_text(result)
    types = {n.get("type", "") for n in result.get("notes", [])}
    red = sum(1 for n in result.get("notes", []) if n.get("flag") == "red")

    if "score_min" in exp and (score is None or score < exp["score_min"]):
        fails.append(f"score {score} < min {exp['score_min']}")
    if "score_max" in exp and (score is None or score > exp["score_max"]):
        fails.append(f"score {score} > max {exp['score_max']}")
    if "min_red_flags" in exp and red < exp["min_red_flags"]:
        fails.append(f"red flags {red} < min {exp['min_red_flags']}")
    if "max_red_flags" in exp and red > exp["max_red_flags"]:
        fails.append(f"red flags {red} > max {exp['max_red_flags']}")
    for sub in exp.get("flag_contains", []):
        if sub.lower() not in text:
            fails.append(f"expected mention of '{sub}'")
    for sub in exp.get("forbid_contains", []):
        if sub.lower() in text:
            fails.append(f"unexpected mention of '{sub}'")
    for t in exp.get("flag_types", []):
        if t not in types:
            fails.append(f"expected a '{t}' note")
    for t in exp.get("forbid_types", []):
        if t in types:
            fails.append(f"unexpected '{t}' note")
    return fails


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="run only samples whose name contains this substring")
    args = parser.parse_args()

    if not get_settings().anthropic_api_key:
        print("ANTHROPIC_API_KEY is not set — the eval makes live review calls.", file=sys.stderr)
        return 2

    samples = yaml.safe_load(GOLDEN.read_text(encoding="utf-8"))
    if args.only:
        samples = [s for s in samples if args.only in s["name"]]
    if not samples:
        print("No samples matched.", file=sys.stderr)
        return 1

    # Reproducible system prompt: fresh in-memory DB seeded from data/reference/,
    # independent of whatever state the dev/prod DB happens to be in.
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        seed(session)
        system_prompt = build_system_prompt(session)

    passed = 0
    for s in samples:
        prompt = build_review_prompt(s["copy"], s.get("format", "general"), s.get("intent", "product"))
        try:
            result, _usage = run_review(system_prompt, prompt)
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL  {s['name']}: review error: {exc}")
            continue
        fails = _evaluate(s, result)
        if fails:
            print(f"FAIL  {s['name']}  (score={result.get('score')})")
            for f in fails:
                print(f"        - {f}")
        else:
            passed += 1
            print(f"PASS  {s['name']}  (score={result.get('score')})")

    total = len(samples)
    print(f"\n{passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
