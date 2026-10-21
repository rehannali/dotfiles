#!/usr/bin/env bash
# One command to set up a machine (macOS Apple Silicon / Intel, Debian-based Linux, WSL2) with Ansible:
#
#   curl -fsSL https://raw.githubusercontent.com/rehannali/dotfiles/main/bootstrap.sh | bash -s -- --host macbook
#
# --host is this machine's name in ansible/inventory/hosts.yml (default: its hostname); that decides what it gets.
# A machine that is not in the inventory yet: add --group mac_personal | mac_work | servers | wsl (default:
# mac_personal on a Mac, servers on Linux).
#
# What it does, in order:
#   1. unlocks sudo once and keeps it unlocked, so nothing later asks for the password again
#   2. macOS: installs the Xcode Command Line Tools without the GUI dialog, then Homebrew on Apple Silicon. Intel
#      Macs get no Homebrew: mycask (tools/mycask, in the repo) installs their apps and tools. Linux: makes sure git
#      and curl exist (apt).
#      Done here, with the real terminal and visible output, so a failure stops with its reason.
#   3. with --bitwarden: logs in to Bitwarden and unlocks the vault (the playbook reads secrets from it)
#   4. clones the repo to ~/.dotfiles (or updates it), installs Ansible (with uv, into its own Python), and runs
#      ansible/site.yml for this machine. Everything that could not be installed is listed at the end.
#   5. if Xcode needs your Apple ID's two-factor code, runs that step last, on your terminal
#
# Options (all optional):
#   --host NAME         this machine in ansible/inventory/hosts.yml (default: its hostname)  (DOTFILES_HOST)
#   --group GROUP       a machine not in the inventory gets what GROUP gets                  (DOTFILES_GROUP)
#   --name "Full Name"  name for git commits (else git_name from the inventory)              (DOTFILES_NAME)
#   --email ADDRESS     email for git commits (else git_email from the inventory)           (DOTFILES_EMAIL)
#   --cli               command-line tools and terminal setup only, no GUI apps (gui_apps=false)
#                                                                                 (DOTFILES_PROFILE=cli)
#   --bitwarden         fetch secrets from Bitwarden, see docs/bitwarden.md       (DOTFILES_BITWARDEN=true)
#   --bw-method M       how to log in to Bitwarden: apikey, sso or password; implies --bitwarden
#                                                                                 (DOTFILES_BW_METHOD)
#   --bw-email ADDRESS  Bitwarden login email, default is --email; implies --bitwarden (DOTFILES_BW_EMAIL)
#   --bw-server URL     self-hosted or EU Bitwarden server; implies --bitwarden   (DOTFILES_BW_SERVER)
#   --no-xcode          no Xcode / simulator runtime (they need your Apple ID)    (DOTFILES_XCODE=skip)
#   --xcode VERSION     this Xcode instead of the newest one this Mac can run     (DOTFILES_XCODE_VERSION)
#   --ios-runtime V     this iOS simulator runtime instead of the one for that Xcode (DOTFILES_IOS_RUNTIME)
#   --no-flutter        no Flutter SDK                                            (DOTFILES_FLUTTER=skip)
#   --no-casks          macOS: no GUI apps from casks (Homebrew, mycask on Intel) (DOTFILES_CASKS=skip)
#   --no-macports       Intel Mac: no MacPorts fallback for tools without a bottle (DOTFILES_MACPORTS=skip)
#   --no-appstore       macOS: no Mac App Store apps (needs a signed-in App Store) (DOTFILES_MAS=skip)
#   --no-defaults       macOS: leave the Dock, Finder and trackpad settings alone (DOTFILES_DEFAULTS=skip)
#   --no-chsh           do not make zsh the login shell                           (DOTFILES_CHSH=skip)
#   --check             show what would change, change nothing (ansible-playbook --check --diff)
#   --branch NAME       use this branch of the repo instead of the default one
#   --source PATH       use a local checkout instead of cloning (it is not pulled) (DOTFILES_SOURCE)
#   -h, --help          this text
#
# Other variables read: DOTFILES_REPO (owner/name, default rehannali/dotfiles), DOTFILES_DIR (where the repo is
# cloned, default ~/.dotfiles), DOTFILES_SKIP_CASKS (casks to leave out, space separated), DOTFILES_ANSIBLE_ARGS
# (extra ansible-playbook options), and for Bitwarden
# BW_CLIENTID and BW_CLIENTSECRET (API key login), BW_PASSWORD (master password, so it is not asked) and BW_SESSION
# (an already unlocked vault). Every variable, by scenario: docs/environment.md
set -euo pipefail

REPO="${DOTFILES_REPO:-rehannali/dotfiles}"
BRANCH=""
SOURCE="${DOTFILES_SOURCE:-}"
HOST="${DOTFILES_HOST:-}"
GROUP="${DOTFILES_GROUP:-}"
CHECK=""

say() { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }
die() { printf '\n\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --host)        [ $# -ge 2 ] || die "--host needs a name"; HOST="$2"; shift ;;
    --group)       [ $# -ge 2 ] || die "--group needs a group"; GROUP="$2"; shift ;;
    --name)        [ $# -ge 2 ] || die "--name needs a value"; export DOTFILES_NAME="$2"; shift ;;
    --email)       [ $# -ge 2 ] || die "--email needs a value"; export DOTFILES_EMAIL="$2"; shift ;;
    --cli)         export DOTFILES_PROFILE=cli ;;
    --full)        export DOTFILES_PROFILE=full ;;
    --bitwarden)   export DOTFILES_BITWARDEN=true ;;
    --bw-method)   [ $# -ge 2 ] || die "--bw-method needs apikey, sso or password"; export DOTFILES_BW_METHOD="$2" DOTFILES_BITWARDEN=true; shift ;;
    --bw-email)    [ $# -ge 2 ] || die "--bw-email needs an address"; export DOTFILES_BW_EMAIL="$2" DOTFILES_BITWARDEN=true; shift ;;
    --bw-server)   [ $# -ge 2 ] || die "--bw-server needs a URL"; export DOTFILES_BW_SERVER="$2" DOTFILES_BITWARDEN=true; shift ;;
    --no-xcode)    export DOTFILES_XCODE=skip ;;
    --xcode)       [ $# -ge 2 ] || die "--xcode needs a version"; export DOTFILES_XCODE_VERSION="$2"; shift ;;
    --ios-runtime) [ $# -ge 2 ] || die "--ios-runtime needs a version"; export DOTFILES_IOS_RUNTIME="$2"; shift ;;
    --no-flutter)  export DOTFILES_FLUTTER=skip ;;
    --no-casks)    export DOTFILES_CASKS=skip ;;
    --no-macports) export DOTFILES_MACPORTS=skip ;;
    --no-appstore) export DOTFILES_MAS=skip ;;
    --no-defaults) export DOTFILES_DEFAULTS=skip ;;
    --no-chsh)     export DOTFILES_CHSH=skip ;;
    --check)       CHECK=1 ;;
    --branch)      [ $# -ge 2 ] || die "--branch needs a value"; BRANCH="$2"; shift ;;
    --source)      [ $# -ge 2 ] || die "--source needs a value"; SOURCE="$2"; shift ;;
    --ansible)     ;;   # Ansible is the only way now; kept so older commands still work
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
  disown "$SUDO_KEEPALIVE_PID" 2> /dev/null || true   # no "Terminated: 15" when cleanup stops it
fi
WORK_TMP="$(mktemp -d)"
cleanup() {
  [ -z "$SUDO_KEEPALIVE_PID" ] || kill "$SUDO_KEEPALIVE_PID" 2> /dev/null || true
  rm -rf "$WORK_TMP"
}
trap cleanup EXIT

as_root() { if [ "$(id -u)" -eq 0 ]; then "$@"; else sudo "$@"; fi; }

# `curl ... | bash` makes stdin the pipe the script itself arrives on: a program that asks something (the Bitwarden
# CLI, Ansible asking for the sudo password, xcodes asking for the two-factor code) would read the end of the pipe instead of
# your keyboard. Give those the terminal. Without a terminal (CI) they keep stdin as it is.
with_tty() {
  if [ ! -t 0 ] && ( : < /dev/tty ) 2> /dev/null; then "$@" < /dev/tty; else "$@"; fi
}

# 2. what has to be there before git and Ansible can run
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

  # Homebrew, Apple Silicon only (/opt/homebrew). Intel Macs have none: Homebrew made them Tier 3 and drops them on
  # 1 September 2027, so mycask (tools/mycask, run by the playbook) installs their apps and tools. It needs only the
  # python3 that came with the Command Line Tools.
  if [ "$(uname -m)" = arm64 ]; then
    brew_bin=/opt/homebrew/bin/brew
    if [ ! -x "$brew_bin" ]; then
      [ "$(id -u)" -ne 0 ] || die "Homebrew will not install as root. Run this as your normal (administrator) user."
      say "Installing Homebrew"
      brew_installer="$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" \
        || die "Could not download the Homebrew installer (no network?)"
      # NONINTERACTIVE: the installer would wait for RETURN. sudo is already unlocked above, so it asks nothing.
      NONINTERACTIVE=1 /bin/bash -c "$brew_installer" \
        || die "The Homebrew installer failed (its output is above). Fix that, then run this again."
    fi
    [ -x "$brew_bin" ] || die "Homebrew is not at $brew_bin after installing it (the installer output above says why)"
    # PATH for everything started from here on: Ansible and what it runs
    eval "$("$brew_bin" shellenv)"
    say "Homebrew: $(brew --version | sed -n 1p) ($brew_bin)"
  else
    /usr/bin/python3 --version > /dev/null 2>&1 || die "/usr/bin/python3 does not run (mycask needs it; it comes with the Command Line Tools)"
    if [ -x /usr/local/bin/brew ] || [ -d /usr/local/Homebrew ]; then
      say "Intel Mac: Homebrew is still in /usr/local; the playbook will stop at the packages and say how to remove it"
    else
      say "Intel Mac: no Homebrew; mycask installs the apps and tools"
    fi
  fi
else
  if ! command -v git > /dev/null 2>&1 || ! command -v curl > /dev/null 2>&1; then
    command -v apt-get > /dev/null 2>&1 || die "git and curl are missing and this is not a Debian-based system"
    say "Installing git and curl"
    as_root env DEBIAN_FRONTEND=noninteractive apt-get update
    as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y git curl ca-certificates
  fi
fi

# 3. Bitwarden, only with --bitwarden
# The playbook reads secrets (secrets.yml, the Apple ID) from the vault, so it has to be open before it starts. The
# CLI is not installed yet at this point: use the official standalone build (it stays on PATH for the run).
bw_install() {
  command -v bw > /dev/null 2>&1 && return 0
  local platform=linux
  [ "$OS" = Darwin ] && platform=macos
  if ! command -v unzip > /dev/null 2>&1; then
    command -v apt-get > /dev/null 2>&1 || die "unzip is needed to unpack the Bitwarden CLI"
    as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y unzip
  fi
  say "Downloading the Bitwarden CLI"
  curl -fsSL "https://vault.bitwarden.com/download/?app=cli&platform=$platform" -o "$WORK_TMP/bw.zip"
  unzip -q -o "$WORK_TMP/bw.zip" -d "$WORK_TMP"
  chmod +x "$WORK_TMP/bw"
  # the macOS download can be an Intel-only binary, which an Apple Silicon Mac runs through Rosetta
  if [ "$OS" = Darwin ] && [ "$(uname -m)" = arm64 ] && ! file "$WORK_TMP/bw" | grep -q arm64; then
    as_root softwareupdate --install-rosetta --agree-to-license > /dev/null 2>&1 || true
  fi
}

bw_state() { bw status 2> /dev/null | sed -n 's/.*"status":"\([a-z]*\)".*/\1/p'; }

bw_open_vault() {
  bw_install
  local state method email cur
  state="$(bw_state)"
  # self-hosted or EU server: the CLI has to know before anything else (it refuses while logged in)
  if [ -n "${DOTFILES_BW_SERVER:-}" ] && [ "$state" = unauthenticated ]; then
    bw config server "$DOTFILES_BW_SERVER" > /dev/null
  elif [ -n "${DOTFILES_BW_SERVER:-}" ]; then
    # the CLI refuses to change the server while logged in; say so instead of quietly using the old one
    cur="$(bw config server 2> /dev/null || true)"
    say "DOTFILES_BW_SERVER is set, but the Bitwarden CLI is already logged in (to ${cur:-its current server}). Run 'bw logout' first to switch servers."
  fi
  if [ "$state" = unauthenticated ]; then
    method="${DOTFILES_BW_METHOD:-}"
    if [ -z "$method" ]; then
      if [ -n "${BW_CLIENTID:-}" ] && [ -n "${BW_CLIENTSECRET:-}" ]; then method=apikey; else method=password; fi
    fi
    say "Logging in to Bitwarden ($method)"
    case "$method" in
      apikey) with_tty bw login --apikey > /dev/null ;;   # reads BW_CLIENTID and BW_CLIENTSECRET
      sso)    with_tty bw login --sso > /dev/null ;;
      password)
        email="${DOTFILES_BW_EMAIL:-${DOTFILES_EMAIL:-}}"
        if [ -z "$email" ]; then read -r -p "Bitwarden email: " email < /dev/tty; fi
        # a login with email and password also unlocks the vault and prints the session key
        if [ -n "${BW_PASSWORD:-}" ]; then
          BW_SESSION="$(with_tty bw login "$email" --passwordenv BW_PASSWORD --raw)"
        else
          BW_SESSION="$(with_tty bw login "$email" --raw)"
        fi
        export BW_SESSION
        ;;
      *) die "DOTFILES_BW_METHOD must be apikey, sso or password, not $method" ;;
    esac
  fi
  if [ -z "${BW_SESSION:-}" ]; then
    say "Unlocking the vault"
    if [ -n "${BW_PASSWORD:-}" ]; then
      BW_SESSION="$(with_tty bw unlock --passwordenv BW_PASSWORD --raw)"
    else
      BW_SESSION="$(with_tty bw unlock --raw)"
    fi
    export BW_SESSION
  fi
  bw sync > /dev/null 2>&1 || true
}

if [ "${DOTFILES_BITWARDEN:-}" = true ]; then bw_open_vault; fi

export PATH="$WORK_TMP:$PATH"   # the Bitwarden CLI, when it was downloaded

# 4. the repo and Ansible
REPO_DIR="${SOURCE:-${DOTFILES_DIR:-$HOME/.dotfiles}}"
if [ -n "$SOURCE" ]; then
  [ -d "$SOURCE/ansible" ] || die "--source $SOURCE is not a checkout of the dotfiles repo"
elif [ -d "$REPO_DIR/.git" ]; then
  # an existing checkout: bring it up to date first, or the old setup is applied again
  say "Updating $REPO_DIR"
  if [ -n "$BRANCH" ]; then
    git -C "$REPO_DIR" fetch --quiet origin "$BRANCH" \
      && { git -C "$REPO_DIR" checkout --quiet "$BRANCH" 2> /dev/null \
           || git -C "$REPO_DIR" checkout --quiet -b "$BRANCH" --track "origin/$BRANCH"; } \
      && git -C "$REPO_DIR" merge --quiet --ff-only "origin/$BRANCH" \
      || printf '\n\033[1;33mWARNING:\033[0m could not update %s to %s (local changes?); using it as it is.\n' "$REPO_DIR" "$BRANCH" >&2
  else
    git -C "$REPO_DIR" pull --quiet --ff-only \
      || printf '\n\033[1;33mWARNING:\033[0m could not update %s (local changes?); using it as it is.\n' "$REPO_DIR" >&2
  fi
else
  say "Cloning $REPO into $REPO_DIR"
  git clone --quiet ${BRANCH:+--branch "$BRANCH"} "https://github.com/$REPO.git" "$REPO_DIR" || die "Could not clone $REPO"
fi
branch="$(git -C "$REPO_DIR" rev-parse --abbrev-ref HEAD)"

# Ansible runs from uv: a Python of its own, nothing goes into the system Python
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv > /dev/null 2>&1; then
  say "Installing uv (for Ansible)"
  installer="$(curl -fsSL https://astral.sh/uv/install.sh)" || die "Could not download the uv installer (no network?)"
  UV_NO_MODIFY_PATH=1 sh -c "$installer" || die "The uv installer failed"
fi
say "Installing Ansible"
# A Python ansible-core supports: uv would otherwise take the newest one it finds (3.15 broke ansible-core's imports).
# uv downloads it if the machine has none.
uv tool install --quiet --upgrade --python 3.13 ansible-core || die "Could not install Ansible"
ansible-galaxy collection install --upgrade -r "$REPO_DIR/ansible/requirements.yml" > /dev/null \
  || die "Could not install the Ansible collections"

# which machine this is
cd "$REPO_DIR/ansible"
export ANSIBLE_CONFIG="$REPO_DIR/ansible/ansible.cfg"
[ -n "$HOST" ] || HOST="$(hostname -s 2> /dev/null || hostname)"
args=(-i inventory/hosts.yml -c local -e "dotfiles_dir=$REPO_DIR" -e "dotfiles_branch=$branch")
if ! ansible-inventory -i inventory/hosts.yml --host "$HOST" > /dev/null 2>&1 || [ -n "$GROUP" ]; then
  if [ -z "$GROUP" ]; then
    if [ "$OS" = Darwin ]; then GROUP=mac_personal; else GROUP=servers; fi
    say "$HOST is not in ansible/inventory/hosts.yml: setting it up like the $GROUP group (--group to choose; add it to the inventory to keep it)"
  fi
  # a machine that is not in the inventory yet: give it the group's setup for this run
  printf 'all:\n  children:\n    %s:\n      hosts:\n        %s:\n' "$GROUP" "$HOST" > "$WORK_TMP/new-host.yml"
  args+=(-i "$WORK_TMP/new-host.yml")
fi
args+=(-l "$HOST")

# options and DOTFILES_* variables -> inventory switches. They are this machine's choices: kept in
# ~/.config/dotfiles/local.yml (dot remember), so every later `dot apply` / `dot sync` uses them too
yaml_str() { local s="${1//\\/\\\\}"; printf '"%s"' "${s//\"/\\\"}"; }
saved=()
choice() { args+=(-e "{\"$1\": $2}"); saved+=("$1: $2"); }
[ -z "$SOURCE" ] || args+=(-e dotfiles_update=false)
[ -z "${DOTFILES_NAME:-}" ] || choice git_name "$(yaml_str "$DOTFILES_NAME")"
[ -z "${DOTFILES_EMAIL:-}" ] || choice git_email "$(yaml_str "$DOTFILES_EMAIL")"
case "${DOTFILES_PROFILE:-}" in cli) choice gui_apps false ;; full) choice gui_apps true ;; esac
[ "${DOTFILES_BITWARDEN:-}" != true ] || choice bitwarden true
[ "${DOTFILES_XCODE:-}" != skip ] || { choice install_xcode false; choice install_ios_runtime false; }
[ "${DOTFILES_RUNTIME:-}" != skip ] || [ "${DOTFILES_XCODE:-}" = skip ] || choice install_ios_runtime false
[ -z "${DOTFILES_XCODE_VERSION:-}" ] || choice xcode_version "$(yaml_str "$DOTFILES_XCODE_VERSION")"
[ -z "${DOTFILES_IOS_RUNTIME:-}" ] || choice ios_runtime "$(yaml_str "$DOTFILES_IOS_RUNTIME")"
[ "${DOTFILES_FLUTTER:-}" != skip ] || choice install_flutter false
case "${DOTFILES_CASKS:-}" in skip | check) choice install_casks false ;; esac
# DOTFILES_SKIP_CASKS="netbird-ui other": apps (names in packages.yml) left out (replaces apps_skip)
if [ -n "${DOTFILES_SKIP_CASKS:-}" ]; then
  skip_list=""
  for c in $DOTFILES_SKIP_CASKS; do skip_list="$skip_list${skip_list:+, }$(yaml_str "$c")"; done
  choice apps_skip "[$skip_list]"
fi
[ "${DOTFILES_MACPORTS:-}" != skip ] || choice macports_fallback false
[ "${DOTFILES_MAS:-}" != skip ] || choice install_app_store false
[ "${DOTFILES_DEFAULTS:-}" != skip ] || choice macos_defaults false
[ "${DOTFILES_CHSH:-}" != skip ] || choice login_shell_zsh false

# keep them, and ask for a git name / email nothing has given yet (not with --check: that changes nothing)
dot_cmd() { DOTFILES_DIR="$REPO_DIR" DOTFILES_HOST="$HOST" DOTFILES_GROUP="$GROUP" bash "$REPO_DIR/home/.local/bin/dot" "$@"; }
if [ -z "$CHECK" ]; then
  if [ ${#saved[@]} -gt 0 ]; then dot_cmd remember "${saved[@]}" || die "Could not save this machine's choices"; fi
  dot_cmd remember || true
fi
local_vars="$HOME/.config/dotfiles/local.yml"
[ ! -f "$local_vars" ] || args+=(-i "$local_vars")
[ -z "$CHECK" ] || args+=(--check --diff)
# DOTFILES_ANSIBLE_ARGS="-e install_casks=false --tags dotfiles": extra ansible-playbook options (word-split)
if [ -n "${DOTFILES_ANSIBLE_ARGS:-}" ]; then read -r -a extra_ansible <<< "$DOTFILES_ANSIBLE_ARGS"; args+=("${extra_ansible[@]}"); fi

# sudo was unlocked in step 1 and is kept unlocked. Where sudo remembers that per terminal (macOS), Ansible's own
# sudo calls may not see it: then Ansible asks for the password once more.
if [ "$(id -u)" -ne 0 ] && [ -z "$CHECK" ] \
    && ! ansible all -i localhost, -c local -b -m ansible.builtin.command -a true > /dev/null 2>&1 < /dev/null; then
  args+=(--ask-become-pass)
fi
say "ansible-playbook site.yml for $HOST${GROUP:+ (group $GROUP)}"
with_tty ansible-playbook "${args[@]}" site.yml

# 5. what needs your terminal: Xcode with an Apple ID that asks for a two-factor code
pending="$HOME/.cache/dotfiles/xcode-install.sh"
if [ -z "$CHECK" ] && [ -x "$pending" ]; then
  if ( : < /dev/tty ) 2> /dev/null; then
    say "Xcode: your Apple ID needs a two-factor code"
    with_tty bash "$pending" || printf '\n\033[1;33mWARNING:\033[0m the Xcode install did not finish; run %s again later.\n' "$pending" >&2
  else
    say "Xcode needs your Apple ID's two-factor code: run $pending on a terminal."
  fi
fi

say "Done. Open a new terminal."
