#!/usr/bin/env bash
# Optional local pre-push hook. Copy it to .git/hooks/pre-push in a repository where
# every push must match a finished mission. Mission Control never installs it.
#
# Set MISSION_PY to the absolute path of scripts/mission.py. MISSION_DIR defaults to .mission.
#
# This is not a sandbox. --no-verify or editing this file bypasses it. A server has
# no access to the local mission state, so this does not work as a server-side hook.
set -u

mission_py=${MISSION_PY:-}
mission_dir=${MISSION_DIR:-.mission}
if [ -z "$mission_py" ]; then
  echo 'mission gate: set MISSION_PY to the path of scripts/mission.py' >&2
  exit 1
fi

failed=0
while read -r _ local_sha remote_ref remote_sha; do
  case "$local_sha" in
    *[!0]*) ;;
    *)
      echo "mission gate: $remote_ref is being deleted; nothing to certify" >&2
      continue
      ;;
  esac
  case "$remote_sha" in
    *[!0]*)
      if ! git merge-base --is-ancestor "$remote_sha" "$local_sha" 2>/dev/null; then
        echo "mission gate: warning: $remote_ref is not a fast-forward; replaced commits are not evaluated" >&2
      fi
      ;;
  esac
  if ! python3 "$mission_py" gate --mission "$mission_dir" --commit "$local_sha" --remote-sha "$remote_sha" >&2; then
    echo "mission gate: $remote_ref not certified for $local_sha" >&2
    failed=1
  fi
done
exit "$failed"
