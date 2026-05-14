#!/usr/bin/env python3
"""
Convert analysis.json to compact YAML for Claude prompts.
Strips fields unused in coding stage (clarification_channel, state_summary,
repo_context, case_id, timestamp) to reduce token consumption.

Usage: python slim_spec.py <analysis.json path>
Output: YAML to stdout
"""
import sys
import json

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

KEEP = ("inferred_target", "technical_specification")
INFERRED_TARGET_DROP = ("confidence",)


def main():
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: slim_spec.py <analysis.json>\n")
        sys.exit(1)

    path = sys.argv[1]
    try:
        # utf-8-sig handles Windows BOM written by PowerShell Out-File
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)
    except Exception as e:
        sys.stderr.write(f"[slim_spec] Failed to read {path}: {e}\n")
        sys.exit(1)

    slim = {k: data[k] for k in KEEP if k in data}

    if "inferred_target" in slim:
        for drop in INFERRED_TARGET_DROP:
            slim["inferred_target"].pop(drop, None)

    if HAS_YAML:
        sys.stdout.write(
            yaml.dump(slim, allow_unicode=True, default_flow_style=False, sort_keys=False)
        )
    else:
        sys.stdout.write(json.dumps(slim, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
