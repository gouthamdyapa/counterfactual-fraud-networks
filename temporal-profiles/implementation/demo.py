#!/usr/bin/env python3
"""Run four small exact-profile examples; optionally save deterministic JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

from profile_solver import select_profile, solve_profiles


_FOLDER = Path(__file__).resolve().parent
_CLASSIFIER_CAVEAT = (
    "The classifier in the first example is hypothetical: it is negative exactly "
    "when W3 == 2. It is not a trained classifier or a full application pipeline. "
    "Terminal selection covers rules that depend only on the reported W2 and W3 "
    "counts and genuinely invariant auxiliary data. A factual class is evaluated "
    "on original counts, before mandatory deletions."
)


def hypothetical_classifier(w2: int, w3: int) -> str:
    """A deliberately nonmonotone count-only rule; w2 is unused by this rule."""
    return "negative" if w3 == 2 else "positive"


def _examples() -> list[tuple[str, str, str, str, Callable[[int, int], bool]]]:
    return [
        (
            "nonmonotone",
            "An intermediate exact W3 value can be the desired class",
            "Deleting a_late leaves W3=2; deleting a_early leaves W3=1. "
            "Both cost 1, but the hypothetical classifier accepts only W3=2.",
            "hypothetical_classifier(w2, w3) == 'negative'",
            lambda w2, w3: hypothetical_classifier(w2, w3) == "negative",
        ),
        (
            "weighted_a",
            "The cheaper A identity can occur later in time",
            "Both A events precede the only B event. Either single deletion "
            "leaves W3=1; deleting a_late_cheap costs 1 instead of 100.",
            "w3 == 1",
            lambda w2, w3: w3 == 1,
        ),
        (
            "weighted_c",
            "Equal-degree C events use the cheapest deletion identity",
            "The two C copies have identical timestamps and B neighborhoods. "
            "Deleting c_second_cheap leaves (W2,W3)=(2,2) at cost 1.",
            "w2 == 2 and w3 == 2",
            lambda w2, w3: w2 == 2 and w3 == 2,
        ),
        (
            "forced_baseline",
            "Mandatory deletion preserves original roles and pays its cost once",
            "Deleting b_forced disconnects the surviving A event. Original "
            "counts are (1,1), baseline counts are (0,0), and total cost is 7.",
            "w2 == 0 and w3 == 0",
            lambda w2, w3: w2 == 0 and w3 == 0,
        ),
    ]


def run_examples() -> dict:
    """Compute the four packaged cases without changing their input files."""
    examples = []
    for name, title, explanation, rule, accept in _examples():
        relative_path = f"examples/{name}.json"
        with (_FOLDER / relative_path).open("r", encoding="utf-8") as stream:
            instance = json.load(stream)
        result = solve_profiles(instance)
        selection = {"rule": rule, "profile": select_profile(result, accept)}
        if name == "nonmonotone":
            original = result["original"]
            baseline = result["baseline"]
            selection["original_factual_class"] = hypothetical_classifier(
                original["w2"], original["w3"]
            )
            selection["baseline_class"] = hypothetical_classifier(
                baseline["w2"], baseline["w3"]
            )
            selection["desired_class"] = "negative"
        examples.append(
            {
                "name": name,
                "title": title,
                "input_file": relative_path,
                "explanation": explanation,
                "result": result,
                "selection": selection,
            }
        )
    return {
        "format_version": 1,
        "count_definition": (
            "W_h counts ordered h-event tuples with chained endpoints, strictly "
            "increasing timestamps, and final target equal to the designated root."
        ),
        "classifier_caveat": _CLASSIFIER_CAVEAT,
        "examples": examples,
    }


def _print_table(profiles: list[dict]) -> None:
    headers = ("loss", "W2", "W3", "optional cost", "total cost", "deleted original IDs")
    rows = [
        (
            str(profile["loss"]),
            str(profile["w2"]),
            str(profile["w3"]),
            str(profile["optional_cost"]),
            str(profile["total_cost"]),
            json.dumps(profile["deleted_ids"], ensure_ascii=False),
        )
        for profile in profiles
    ]
    widths = [max(len(header), *(len(row[index]) for row in rows)) for index, header in enumerate(headers)]
    print("  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    for row in rows:
        print("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


def print_report(report: dict) -> None:
    print("EXACT ATTAINABLE ROOT-ENDING WALK PROFILES")
    print(report["count_definition"])
    for number, example in enumerate(report["examples"], start=1):
        result = example["result"]
        print(f"\n{number}. {example['title']}")
        print(f"Input: {example['input_file']}")
        print(example["explanation"])
        print(
            f"Status: {result['status']}; original (W2,W3)="
            f"({result['original']['w2']},{result['original']['w3']}); baseline="
            f"({result['baseline']['w2']},{result['baseline']['w3']})"
        )
        print(
            f"Normalized min_w2={result['min_w2']}; R={result['R']}; "
            f"forced cost={result['forced_cost']}"
        )
        if result["profiles"]:
            _print_table(result["profiles"])
        else:
            print(f"No profiles: {result['reason']}")
        selection = example["selection"]
        print(f"Selection rule: {selection['rule']}")
        if "original_factual_class" in selection:
            print(
                f"Original factual class: {selection['original_factual_class']}; "
                f"desired class: {selection['desired_class']}"
            )
        chosen = selection["profile"]
        if chosen is None:
            print("Selected profile: none")
        else:
            print(
                f"Selected: (W2,W3)=({chosen['w2']},{chosen['w3']}), "
                f"total cost={chosen['total_cost']}, deleted IDs="
                f"{json.dumps(chosen['deleted_ids'], ensure_ascii=False)}"
            )
    print(f"\nClassifier scope: {report['classifier_caveat']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="also write deterministic JSON containing every result and selection",
    )
    args = parser.parse_args(argv)
    try:
        report = run_examples()
        print_report(report)
        if args.output is not None:
            with args.output.open("w", encoding="utf-8") as stream:
                json.dump(report, stream, ensure_ascii=False, sort_keys=True, indent=2)
                stream.write("\n")
            print(f"\nSaved JSON: {args.output}")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
