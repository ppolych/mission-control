#!/usr/bin/env bash
# Run every local check. Use it on each platform, since there is no hosted CI.
set -eu

root=$(cd "$(dirname "$0")/.." && pwd)
cd "$root"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

echo "== platform: $(uname -sr), $(python3 --version)"

export MISSION_REQUIRE_SHELLS=1
echo "== unit tests, with more random lifecycle seeds"
MISSION_RANDOM_SEEDS=200 python3 -m unittest discover -s tests

echo "== unit tests with a symlinked temp directory, as on macOS"
mkdir "$work/real"
ln -s "$work/real" "$work/link"
TMPDIR="$work/link" python3 -m unittest discover -s tests

echo "== behavioral probes"
python3 evals/run_behavioral.py --baseline evals/baseline-control-plane.json >/dev/null
python3 -O evals/run_behavioral.py --baseline evals/baseline-control-plane.json >/dev/null

echo "== template and shell syntax"
python3 scripts/mission.py validate --contract templates/contract.json
bash -n scripts/verify.sh scripts/no_progress.sh evals/check_all.sh
if command -v shellcheck >/dev/null; then
  shellcheck scripts/*.sh evals/check_all.sh
else
  echo "shellcheck not installed; skipped"
fi

echo "== packaging"
python3 scripts/package_release.py --output "$work/mission-control.zip"

echo "== all checks passed"
