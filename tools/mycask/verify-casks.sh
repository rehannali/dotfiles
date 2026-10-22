#!/bin/bash
# Install every cask in a list with mycask, one at a time, check each from its receipt (verify.py), and uninstall it
# again, so a runner with a small disk can go through about 90 apps. Used by .github/workflows/mycask-verify.yml.
#
#   verify-casks.sh tools/mycask/intel/casks.txt report.md
#
# A line is "token" or "token --appdir=DIR" (as in mycask bundle). Apps already on the runner are taken over (--adopt).
# Each cask gets MYCASK_CASK_TIMEOUT seconds (default 1500). Exit status 1 when any cask failed; the report is Markdown.
set -u

list="${1:?usage: verify-casks.sh casks.txt report.md}"
report="${2:?usage: verify-casks.sh casks.txt report.md}"
here="$(cd "$(dirname "$0")" && pwd)"
mycask_py="${MYCASK_PY:-$here/mycask.py}"
verify_py="${VERIFY_PY:-$here/verify.py}"
limit="${MYCASK_CASK_TIMEOUT:-1500}"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

mkdir -p "$HOME/Applications"
: > "$work/rows"
: > "$work/errors"
total=0
bad=0

while IFS= read -r line; do
  line="${line%%#*}"
  # shellcheck disable=SC2086   # a line is "token [--appdir=DIR]": split on purpose
  set -- $line
  [ $# -gt 0 ] || continue
  token="$1"
  shift
  opts=()
  for o in "$@"; do opts+=("${o/#--appdir=\~/--appdir=$HOME}"); done
  total=$((total + 1))

  echo "::group::$token"
  echo "$token" > "$work/one.txt"
  log="$work/$token.log"
  # perl: macOS has no timeout(1); alarm kills the install when it hangs (an installer waiting for input)
  for _ in 1 2; do
    perl -e 'alarm shift; exec @ARGV' "$limit" /usr/bin/python3 -I "$mycask_py" install --adopt ${opts[@]+"${opts[@]}"} "$token" > "$log" 2>&1
    rc=$?
    # one more try after a failed download (a slow or reset connection), never after anything else
    if [ "$rc" -eq 0 ] || ! grep -q 'curl .*' "$log" || ! grep -q 'command failed (' "$log"; then break; fi
    echo "download failed, trying $token once more"
  done
  if [ "$rc" -ne 0 ]; then
    why="$(grep -m1 '^Error:' "$log" || true)"
    echo "| $token | install | ${why:-exit status $rc} |" >> "$work/errors"
  fi
  tail -n 5 "$log"

  /usr/bin/python3 -I "$verify_py" --casks "$work/one.txt" > "$work/check.txt" 2>&1 || bad=$((bad + 1))
  grep -E "^\| $token \|" "$work/check.txt" >> "$work/rows" || echo "| $token | cask | FAIL | verify.py gave no result |" >> "$work/rows"
  grep -E "^\| $token \|" "$work/check.txt" || cat "$work/check.txt"

  # leave the disk free for the next one; not --zap, nothing of the user's is involved on a runner
  /usr/bin/python3 -I "$mycask_py" uninstall "$token" > /dev/null 2>&1 || true
  echo "::endgroup::"
done < "$list"

{
  echo "| | kind | status | detail |"
  echo "|---|---|---|---|"
  grep -F '| FAIL |' "$work/rows" || true
  grep -vF '| FAIL |' "$work/rows" || true
  echo
  echo "$((total - bad)) of $total casks verified, $bad failed"
  if [ -s "$work/errors" ]; then
    echo
    echo "Install errors:"
    echo
    echo "| cask | step | error |"
    echo "|---|---|---|"
    cat "$work/errors"
  fi
} > "$report"
cat "$report"
[ "$bad" -eq 0 ]
