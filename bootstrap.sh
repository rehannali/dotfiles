#!/usr/bin/env bash
# One command to set up a machine (macOS Apple Silicon / Intel, Debian-based Linux, WSL2):
#
#   curl -fsSL https://raw.githubusercontent.com/rehannali/dotfiles/main/bootstrap.sh | bash
#   curl -fsSL https://raw.githubusercontent.com/rehannali/dotfiles/main/bootstrap.sh | bash -s -- --cli
#
# What it does, in order:
#   1. unlocks sudo once and keeps it unlocked, so nothing later asks for the password again
#   2. macOS: installs the Xcode Command Line Tools without the GUI dialog.
#      Linux:  makes sure git and curl exist (apt).
#      This has to happen first: on a bare Mac the first `git` call, which `chezmoi init <repo>` makes, is
#      what opens the "install developer tools" dialog and aborts.
#   3. downloads chezmoi into a temp dir (nothing is left in $HOME)
#   4. runs `chezmoi init --apply`, which does everything else
#
# Options (all optional; anything you leave out is asked once by chezmoi on your terminal):
#   --name "Full Name"  name for git commits                                      (DOTFILES_NAME)
#   --email ADDRESS     email for git commits                                     (DOTFILES_EMAIL)
#   --cli | --full      profile: command-line tools and terminal setup only (servers), or everything (default)
#                                                                                 (DOTFILES_PROFILE)
#   --bitwarden         fetch secrets from Bitwarden, see "Bitwarden" in the README   (DOTFILES_BITWARDEN=true)
#   --no-xcode          do not install Xcode / the simulator runtime (they need your Apple ID)
#                                                                                 (DOTFILES_XCODE=skip)
#   --no-flutter        do not install the Flutter SDK with fvm                  (DOTFILES_FLUTTER=skip)
#   --no-casks          macOS: only check the cask list, install none            (DOTFILES_CASKS=check)
#   --no-appstore       macOS: skip Mac App Store apps (needs a signed-in App Store) (DOTFILES_MAS=skip)
#   --branch NAME       use this branch of the repo instead of the default one
#   --source PATH       use a local checkout instead of GitHub                    (DOTFILES_SOURCE)
#   -h, --help          this text
#
# Other variables read: DOTFILES_REPO (owner/name, default rehannali/dotfiles), DOTFILES_CHEZMOI_ARGS (extra
# flags for chezmoi, e.g. --verbose), and for Bitwarden BW_CLIENTID, BW_CLIENTSECRET, BW_PASSWORD,
# DOTFILES_BW_METHOD (apikey | sso | password), DOTFILES_BW_EMAIL and DOTFILES_BW_SERVER (self-hosted URL).
set -euo pipefail

REPO="${DOTFILES_REPO:-rehannali/dotfiles}"
BRANCH=""
SOURCE="${DOTFILES_SOURCE:-}"

say() { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }
die() { printf '\n\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --name)        [ $# -ge 2 ] || die "--name needs a value"; export DOTFILES_NAME="$2"; shift ;;
    --bitwarden)   export DOTFILES_BITWARDEN=true ;;
    --cli)         export DOTFILES_PROFILE=cli ;;
    --full)        export DOTFILES_PROFILE=full ;;
    --email)       [ $# -ge 2 ] || die "--email needs a value"; export DOTFILES_EMAIL="$2"; shift ;;
    --no-xcode)    export DOTFILES_XCODE=skip ;;
    --no-flutter)  export DOTFILES_FLUTTER=skip ;;
    --no-casks)    export DOTFILES_CASKS=check ;;
    --no-appstore) export DOTFILES_MAS=skip ;;
    --branch)      [ $# -ge 2 ] || die "--branch needs a value"; BRANCH="$2"; shift ;;
    --source)      [ $# -ge 2 ] || die "--source needs a value"; SOURCE="$2"; shift ;;
    -h | --help)   sed -n '2,/^set -euo/p' "$0" | sed '$d;s/^# \{0,1\}//'; exit 0 ;;
    *)             die "unknown option: $1 (try --help)" ;;
  esac
  shift
done

OS="$(uname -s)"
case "$OS" in Darwin | Linux) ;; *) die "unsupported OS: $OS (Windows: see the README)" ;; esac

# 1. sudo, once
SUDO_KEEPALIVE_PID=""
if [ "$(id -u)" -ne 0 ]; then
  command -v sudo > /dev/null 2>&1 || die "sudo is required (or run this as root)"
  say "Unlocking sudo (asked once; it stays unlocked while this runs)"
  sudo -v
  ( while true; do sudo -n true 2> /dev/null || exit; sleep 50; kill -0 "$$" 2> /dev/null || exit; done ) &
  SUDO_KEEPALIVE_PID=$!
fi
CHEZMOI_TMP="$(mktemp -d)"
cleanup() {
  [ -z "$SUDO_KEEPALIVE_PID" ] || kill "$SUDO_KEEPALIVE_PID" 2> /dev/null || true
  rm -rf "$CHEZMOI_TMP"
}
trap cleanup EXIT

as_root() { if [ "$(id -u)" -eq 0 ]; then "$@"; else sudo "$@"; fi; }

# 2. what chezmoi needs before it can start
if [ "$OS" = Darwin ]; then
  if ! xcode-select -p > /dev/null 2>&1; then
    say "Installing the Xcode Command Line Tools (no dialog)"
    # The trigger file makes softwareupdate list the CLT as an installable update; this is the same route
    # Homebrew's installer takes.
    trigger=/tmp/.com.apple.dt.CommandLineTools.installondemand.in-progress-file
    touch "$trigger"
    # (|| label="": grep finding nothing must not end the script under set -e / pipefail)
    label="$(softwareupdate -l 2> /dev/null | grep -B 1 -E 'Command Line Tools' | awk -F'*' '/^ *\*/ {print $2}' \
      | sed -e 's/^ *Label: //' -e 's/^ *//' | sort -V | tail -n1)" || label=""
    if [ -n "$label" ]; then
      as_root softwareupdate -i "$label" --verbose || true
      as_root xcode-select --switch /Library/Developer/CommandLineTools || true
    fi
    rm -f "$trigger"
  fi
  if ! xcode-select -p > /dev/null 2>&1; then
    say "Headless install did not work; opening the system dialog instead (click Install)"
    xcode-select --install > /dev/null 2>&1 || true
    waited=0
    until xcode-select -p > /dev/null 2>&1; do
      sleep 6; waited=$((waited + 6))
      [ "$waited" -lt 1800 ] || die "timed out waiting for the Command Line Tools"
    done
  fi
  say "Command Line Tools: $(xcode-select -p)"
else
  if ! command -v git > /dev/null 2>&1 || ! command -v curl > /dev/null 2>&1; then
    command -v apt-get > /dev/null 2>&1 || die "git and curl are missing and this is not a Debian-based system"
    say "Installing git and curl"
    as_root env DEBIAN_FRONTEND=noninteractive apt-get update
    as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y git curl ca-certificates
  fi
fi

# 3. chezmoi
say "Downloading chezmoi"
sh -c "$(curl -fsLS get.chezmoi.io)" -- -b "$CHEZMOI_TMP"
export PATH="$CHEZMOI_TMP:$PATH"

# Bitwarden, only with --bitwarden
# chezmoi reads secrets while it renders templates, which is before any script of the dotfiles has run, so the
# vault has to be open before `chezmoi init`. The CLI is not installed yet at this point: use the official
# standalone build.
bw_install() {
  command -v bw > /dev/null 2>&1 && return 0
  local platform=linux
  [ "$OS" = Darwin ] && platform=macos
  if ! command -v unzip > /dev/null 2>&1; then
    command -v apt-get > /dev/null 2>&1 || die "unzip is needed to unpack the Bitwarden CLI"
    as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y unzip
  fi
  say "Downloading the Bitwarden CLI"
  curl -fsSL "https://vault.bitwarden.com/download/?app=cli&platform=$platform" -o "$CHEZMOI_TMP/bw.zip"
  unzip -q -o "$CHEZMOI_TMP/bw.zip" -d "$CHEZMOI_TMP"
  chmod +x "$CHEZMOI_TMP/bw"
  # the macOS download can be an Intel-only binary, which an Apple Silicon Mac runs through Rosetta
  if [ "$OS" = Darwin ] && [ "$(uname -m)" = arm64 ] && ! file "$CHEZMOI_TMP/bw" | grep -q arm64; then
    as_root softwareupdate --install-rosetta --agree-to-license > /dev/null 2>&1 || true
  fi
}

bw_state() { bw status 2> /dev/null | sed -n 's/.*"status":"\([a-z]*\)".*/\1/p'; }

bw_open_vault() {
  bw_install
  local state method email
  state="$(bw_state)"
  # self-hosted or EU server: the CLI has to know before anything else (it refuses while logged in)
  if [ -n "${DOTFILES_BW_SERVER:-}" ] && [ "$state" = unauthenticated ]; then
    bw config server "$DOTFILES_BW_SERVER" > /dev/null
  fi
  if [ "$state" = unauthenticated ]; then
    method="${DOTFILES_BW_METHOD:-}"
    if [ -z "$method" ]; then
      if [ -n "${BW_CLIENTID:-}" ] && [ -n "${BW_CLIENTSECRET:-}" ]; then method=apikey; else method=password; fi
    fi
    say "Logging in to Bitwarden ($method)"
    case "$method" in
      apikey) bw login --apikey > /dev/null ;;   # reads BW_CLIENTID and BW_CLIENTSECRET
      sso)    bw login --sso > /dev/null ;;
      password)
        email="${DOTFILES_BW_EMAIL:-${DOTFILES_EMAIL:-}}"
        if [ -z "$email" ]; then read -r -p "Bitwarden email: " email < /dev/tty; fi
        # a login with email and password also unlocks the vault and prints the session key
        if [ -n "${BW_PASSWORD:-}" ]; then
          BW_SESSION="$(bw login "$email" --passwordenv BW_PASSWORD --raw)"
        else
          BW_SESSION="$(bw login "$email" --raw)"
        fi
        export BW_SESSION
        ;;
      *) die "DOTFILES_BW_METHOD must be apikey, sso or password, not $method" ;;
    esac
  fi
  if [ -z "${BW_SESSION:-}" ]; then
    say "Unlocking the vault"
    if [ -n "${BW_PASSWORD:-}" ]; then
      BW_SESSION="$(bw unlock --passwordenv BW_PASSWORD --raw)"
    else
      BW_SESSION="$(bw unlock --raw)"
    fi
    export BW_SESSION
  fi
  bw sync > /dev/null 2>&1 || true
}

if [ "${DOTFILES_BITWARDEN:-}" = true ]; then bw_open_vault; fi

# 4. everything else
# Extra chezmoi flags, e.g. DOTFILES_CHEZMOI_ARGS="--verbose" (CI uses it for a readable log)
extra=()
if [ -n "${DOTFILES_CHEZMOI_ARGS:-}" ]; then read -r -a extra <<< "$DOTFILES_CHEZMOI_ARGS"; fi

# ${extra[@]+...}: macOS bash 3.2 treats an empty array as unset under `set -u`
if [ -n "$SOURCE" ]; then
  say "chezmoi init --apply (from $SOURCE)"
  chezmoi init --source "$SOURCE" --apply ${extra[@]+"${extra[@]}"}
elif [ -n "$BRANCH" ]; then
  say "chezmoi init --apply $REPO (branch $BRANCH)"
  chezmoi init --apply --branch "$BRANCH" ${extra[@]+"${extra[@]}"} "$REPO"
else
  say "chezmoi init --apply $REPO"
  chezmoi init --apply ${extra[@]+"${extra[@]}"} "$REPO"
fi

say "Done. Open a new terminal."
