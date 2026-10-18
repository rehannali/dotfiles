#!/usr/bin/env bash
# Makes the FASTLANE_SESSION value on this machine, no CI and no relay involved, and can save it as the
# repository secret. Works on macOS and Linux (WSL is fine): fastlane only talks to Apple's web service.
#
#   scripts/apple-session.sh you@example.com           sign in, print the session
#   scripts/apple-session.sh you@example.com --save    also run `gh secret set FASTLANE_SESSION`
#
# Needs Ruby 3.3 or newer. If the Ruby on PATH is missing or older, mise's Ruby 3.3 is used when mise is
# installed (it is fetched on demand, nothing global changes). fastlane is installed into a temporary folder
# and removed again; nothing is left on the machine. You type your Apple ID password and the two-factor code; the session
# is valid for about a month.
set -euo pipefail

# no usage analytics and no update check from fastlane
export FASTLANE_OPT_OUT_USAGE=YES FASTLANE_SKIP_UPDATE_CHECK=1

APPLE_ID="${1:-}"
SAVE="${2:-}"
if [ -z "$APPLE_ID" ] || [ "${APPLE_ID#-}" != "$APPLE_ID" ]; then
  sed -n '2,/^set -euo/p' "$0" | sed '$d;s/^# \{0,1\}//'
  exit 1
fi
# fastlane wants Ruby 3.3+
ruby_cmd=()
if ! command -v ruby > /dev/null 2>&1 \
    || ! ruby -e 'exit(Gem::Version.new(RUBY_VERSION) >= Gem::Version.new("3.3") ? 0 : 1)' 2> /dev/null; then
  if command -v mise > /dev/null 2>&1; then
    ruby_cmd=(mise exec ruby@3.3 --)
  else
    echo "Needs Ruby 3.3 or newer, and found none. Install mise (https://mise.run) or Ruby and try again." >&2
    exit 1
  fi
fi

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
chmod 700 "$work"

echo "Installing fastlane into a temporary folder..."
GEM_HOME="$work/gems" GEM_PATH="$work/gems" ${ruby_cmd[@]+"${ruby_cmd[@]}"} gem install fastlane --no-document --silent
out="$work/spaceauth.txt"

# fastlane's launcher script in gems/bin looks for a ruby next to itself, which a temporary GEM_HOME doesn't have,
# so start the real entry point with ruby instead
entry=""
for entry in "$work"/gems/gems/fastlane-*/bin/fastlane; do :; done
[ -f "$entry" ] || { echo "fastlane did not install" >&2; exit 1; }

# The prompts (password, code) have to reach you, so the output is shown as it goes and kept in a private file
GEM_HOME="$work/gems" GEM_PATH="$work/gems" ${ruby_cmd[@]+"${ruby_cmd[@]}"} ruby "$entry" spaceauth -u "$APPLE_ID" | tee "$out"

# fastlane prints: "Pass the following via the FASTLANE_SESSION environment variable:" then the value, which
# starts with --- and runs to the next blank line
session="$(awk '/FASTLANE_SESSION environment variable/ {on = 1; next} on && /^---/ {grab = 1} grab && /^$/ {exit} grab {print}' "$out")"

if [ -z "$session" ]; then
  echo "Could not find the session in the output above. Copy it by hand (from --- to the blank line)." >&2
  exit 1
fi

if [ "$SAVE" = "--save" ]; then
  command -v gh > /dev/null 2>&1 || { echo "gh is not installed; copy the value above by hand." >&2; exit 1; }
  printf '%s\n' "$session" | gh secret set FASTLANE_SESSION
  echo "Saved as the repository secret FASTLANE_SESSION."
else
  echo
  echo "Save it with:  scripts/apple-session.sh $APPLE_ID --save   (asks for the code again)"
  echo "or paste the value into:  gh secret set FASTLANE_SESSION"
fi
