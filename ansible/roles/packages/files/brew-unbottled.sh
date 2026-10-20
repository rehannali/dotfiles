#!/usr/bin/env bash
# brew-unbottled.sh FORMULA PREBUILT
# Prints the formulae among FORMULA and its runtime dependencies that are not installed and have no bottle this
# Intel Mac can use (nothing printed: it installs without compiling). PREBUILT=true leaves FORMULA itself out (a
# tap formula that downloads a ready-made binary). Homebrew builds no new Intel bottles (Tier 3), and
# `brew install --force-bottle` compiles dependencies that have none, so every one is checked first.
set -uo pipefail
formula="$1"
prebuilt="${2:-false}"

major="$(sw_vers -productVersion | cut -d. -f1)"
tags=""
for entry in tahoe:26 sequoia:15 sonoma:14 ventura:13 monterey:12 big_sur:11; do
  if [ "$major" -ge "${entry#*:}" ]; then tags="$tags ${entry%%:*}"; fi   # bottles for older macOS are usable
done
# shellcheck disable=SC2086  # $tags is a space-separated word list
tag_re="\"(all$(printf '|%s' $tags))\":[[:space:]]*\\{"

has_bottle() {
  local json
  json="$(brew info --json=v2 --formula "$1" 2> /dev/null)" || return 1
  grep -Eq "$tag_re" <<< "$json"
}

missing=""
for dep in $([ "$prebuilt" = true ] || echo "$formula") $(brew deps --formula "$formula" 2> /dev/null); do
  brew list --formula "$dep" > /dev/null 2>&1 && continue
  has_bottle "$dep" || missing="$missing $dep"
done
echo "${missing# }"
