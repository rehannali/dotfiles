#!/usr/bin/env bash
# One command to set up a machine (macOS Apple Silicon / Intel, Debian-based Linux, WSL2):
#
#   curl -fsSL https://raw.githubusercontent.com/rehannali/dotfiles/main/bootstrap.sh | bash
#   curl -fsSL https://raw.githubusercontent.com/rehannali/dotfiles/main/bootstrap.sh | bash -s -- --cli
#
# What it does, in order:
#   1. unlocks sudo once and keeps it unlocked, so nothing later asks for the password again
#   2. macOS: installs the Xcode Command Line Tools without the GUI dialog, then Homebrew (on Intel by hand: the
#      official installer refuses Intel Macs).
#      Linux:  makes sure git and curl exist (apt).
#      This has to happen first: on a bare Mac the first `git` call, which `chezmoi init <repo>` makes, is
#      what opens the "install developer tools" dialog and aborts. Homebrew is installed here, with the real
#      terminal and visible output, so a failure stops the run with its reason instead of showing up later as
#      "brew: command not found".
#   3. downloads chezmoi into a temp dir (nothing is left in $HOME)
#   4. runs `chezmoi init --apply`, which does everything else. It gets your terminal as its input even when
#      this script came through a pipe (curl ... | bash), so xcodes can ask for the Apple two-factor code.
#
# Options (all optional; anything you leave out is asked once by chezmoi on your terminal):
#   --name "Full Name"  name for git commits                                      (DOTFILES_NAME)
#   --email ADDRESS     email for git commits                                     (DOTFILES_EMAIL)
#   --cli | --full      profile: command-line tools and terminal setup only (servers), or everything (default)
#                                                                                 (DOTFILES_PROFILE)
#   --bitwarden         fetch secrets from Bitwarden, see "Bitwarden" in the README   (DOTFILES_BITWARDEN=true)
#   --bw-method M       how to log in to Bitwarden: apikey, sso or password; implies --bitwarden
#                                                                                 (DOTFILES_BW_METHOD)
#   --bw-email ADDRESS  Bitwarden login email, default is --email; implies --bitwarden (DOTFILES_BW_EMAIL)
#   --bw-server URL     self-hosted or EU Bitwarden server; implies --bitwarden   (DOTFILES_BW_SERVER)
#   --no-xcode          do not install Xcode / the simulator runtime (they need your Apple ID)
#                                                                                 (DOTFILES_XCODE=skip)
#   --xcode VERSION     install this Xcode instead of the newest one this Mac can run (DOTFILES_XCODE_VERSION)
#   --ios-runtime V     install this iOS simulator runtime instead of the one for that Xcode
#                                                                                 (DOTFILES_IOS_RUNTIME)
#   --no-flutter        do not install the Flutter SDK with fvm                  (DOTFILES_FLUTTER=skip)
#   --no-casks          macOS: only check the cask list, install none            (DOTFILES_CASKS=check)
#   --no-macports       Intel Mac: do not fall back to MacPorts for tools Homebrew has no bottle for
#                                                                                 (DOTFILES_MACPORTS=skip)
#   --no-appstore       macOS: skip Mac App Store apps (needs a signed-in App Store) (DOTFILES_MAS=skip)
#   --no-defaults       macOS: leave the Dock, Finder and trackpad settings alone    (DOTFILES_DEFAULTS=skip)
#   --no-chsh           do not make zsh the login shell (that step needs sudo)        (DOTFILES_CHSH=skip)
#   --branch NAME       use this branch of the repo instead of the default one
#   --source PATH       use a local checkout instead of GitHub                    (DOTFILES_SOURCE)
#   -h, --help          this text
#
# Other variables read: DOTFILES_REPO (owner/name, default rehannali/dotfiles), DOTFILES_CHEZMOI_ARGS (extra
# flags for chezmoi, e.g. --verbose), DOTFILES_CHEZMOI_VERSION (a chezmoi release tag such as v2.73.2 instead of the
# latest), and for Bitwarden BW_CLIENTID and BW_CLIENTSECRET (API key login), BW_PASSWORD (master password, so it is
# not asked) and BW_SESSION (an already unlocked vault). Every variable, by scenario: docs/environment.md
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
    --bw-method)   [ $# -ge 2 ] || die "--bw-method needs apikey, sso or password"; export DOTFILES_BW_METHOD="$2" DOTFILES_BITWARDEN=true; shift ;;
    --bw-email)    [ $# -ge 2 ] || die "--bw-email needs an address"; export DOTFILES_BW_EMAIL="$2" DOTFILES_BITWARDEN=true; shift ;;
    --bw-server)   [ $# -ge 2 ] || die "--bw-server needs a URL"; export DOTFILES_BW_SERVER="$2" DOTFILES_BITWARDEN=true; shift ;;
    --cli)         export DOTFILES_PROFILE=cli ;;
    --full)        export DOTFILES_PROFILE=full ;;
    --email)       [ $# -ge 2 ] || die "--email needs a value"; export DOTFILES_EMAIL="$2"; shift ;;
    --no-xcode)    export DOTFILES_XCODE=skip ;;
    --xcode)       [ $# -ge 2 ] || die "--xcode needs a version"; export DOTFILES_XCODE_VERSION="$2"; shift ;;
    --ios-runtime) [ $# -ge 2 ] || die "--ios-runtime needs a version"; export DOTFILES_IOS_RUNTIME="$2"; shift ;;
    --no-flutter)  export DOTFILES_FLUTTER=skip ;;
    --no-casks)    export DOTFILES_CASKS=check ;;
    --no-macports) export DOTFILES_MACPORTS=skip ;;
    --no-appstore) export DOTFILES_MAS=skip ;;
    --no-defaults) export DOTFILES_DEFAULTS=skip ;;
    --no-chsh)     export DOTFILES_CHSH=skip ;;
    --branch)      [ $# -ge 2 ] || die "--branch needs a value"; BRANCH="$2"; shift ;;
    --source)      [ $# -ge 2 ] || die "--source needs a value"; SOURCE="$2"; shift ;;
    -h | --help)   sed -n '2,/^set -euo/p' "$0" | sed '$d;s/^# \{0,1\}//'; exit 0 ;;
    *)             die "unknown option: $1 (try --help)" ;;
  esac
  shift
done

OS="$(uname -s)"
case "$OS" in Darwin | Linux) ;; *) die "unsupported OS: $OS (Windows: see the README)" ;; esac

# Homebrew's installer (install.sh) and its .pkg refuse every Intel Mac now ("only supported on Apple Silicon
# processors"), but brew itself still runs there (Tier 3, supported until September 2027). Intel gets what the old
# installer did: a checkout of Homebrew/brew in /usr/local/Homebrew, linked as /usr/local/bin/brew, then
# `brew update` fetches the formula index (it comes from the API, nothing else is cloned).
# BREW_PREFIX (default /usr/local) and BREW_GROUP (default admin) are only changed by a test.

# Homebrew's own installer prepares /usr/local like this, and the manual install has to end up the same: every
# directory brew writes into exists, belongs to you and the admin group, and is group-writable (the directories zsh
# reads completions from stay 755: group-writable ones make compinit complain about insecure directories). On a Mac
# that had /usr/local before Homebrew, some of these (lib/pkgconfig, share/man/man8, ...) belong to root and brew then
# warns "directories not writable by your user". The list is install.sh's plus brew's own
# (Keg.must_be_writable_directories and must_exist_subdirectories). Runs every time, also when brew is already installed.
dir_group() { stat -f %Sg "$1" 2> /dev/null || stat -c %G "$1"; }   # macOS, then GNU stat

brew_fix_intel_dirs() {
  local prefix="${BREW_PREFIX:-/usr/local}" group="${BREW_GROUP:-admin}" me dir target
  me="$(id -un)"
  for dir in bin etc etc/bash_completion.d include lib lib/cps lib/pkgconfig sbin opt Cellar Caskroom Frameworks \
      share share/aclocal share/doc share/info share/locale share/man share/man/man1 share/man/man2 share/man/man3 \
      share/man/man4 share/man/man5 share/man/man6 share/man/man7 share/man/man8 share/cps share/zsh \
      share/zsh/site-functions share/fish share/fish/vendor_completions.d share/fish/vendor_functions.d share/pwsh \
      share/pwsh/completions var var/log var/homebrew var/homebrew/linked var/homebrew/locks; do
    target="$prefix/$dir"
    [ -d "$target" ] || as_root mkdir -p "$target"
    [ -O "$target" ] || as_root chown "$me" "$target"
    [ "$(dir_group "$target")" = "$group" ] || as_root chgrp "$group" "$target"
    case "$dir" in
      share/zsh | share/zsh/site-functions) as_root chmod 755 "$target" ;;
      *) as_root chmod u+rwx,g+rwx "$target" ;;
    esac
  done
  # the checkout of Homebrew/brew itself, and the Python packages brew installs (lib/pythonX.Y/site-packages)
  for target in "$prefix/Homebrew" "$prefix"/lib/python*/site-packages; do
    [ -d "$target" ] || continue
    { [ -O "$target" ] && [ "$(dir_group "$target")" = "$group" ]; } || as_root chown -R "$me:$group" "$target"
  done
}

brew_install_intel() {
  local prefix="${BREW_PREFIX:-/usr/local}"
  command -v git > /dev/null 2>&1 || die "git is needed to install Homebrew"
  brew_fix_intel_dirs
  if [ ! -d "$prefix/Homebrew/.git" ]; then
    # /usr/local belongs to root: the checkout's directory is made (and handed over) with sudo, like the installer does
    as_root mkdir -p "$prefix/Homebrew"
    as_root chown -R "$(id -un):${BREW_GROUP:-admin}" "$prefix/Homebrew"
    git clone --quiet https://github.com/Homebrew/brew "$prefix/Homebrew" \
      || die "Could not download Homebrew from github.com/Homebrew/brew"
  fi
  ln -sf "$prefix/Homebrew/bin/brew" "$prefix/bin/brew"
  "$prefix/bin/brew" update --force --quiet || die "brew update failed (its output is above)"
}

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

# `curl ... | bash` makes stdin the pipe the script itself arrives on: a program that asks something (the Bitwarden
# CLI, chezmoi's prompts, xcodes asking for the two-factor code) would read the end of the pipe instead of
# your keyboard. Give those the terminal. Without a terminal (CI) they keep stdin as it is.
with_tty() {
  if [ ! -t 0 ] && ( : < /dev/tty ) 2> /dev/null; then "$@" < /dev/tty; else "$@"; fi
}

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

  # Homebrew. Apple Silicon: /opt/homebrew, Intel: /usr/local.
  if [ "$(uname -m)" = arm64 ]; then brew_bin=/opt/homebrew/bin/brew; else brew_bin=/usr/local/bin/brew; fi
  if [ ! -x "$brew_bin" ]; then
    [ "$(id -u)" -ne 0 ] || die "Homebrew will not install as root. Run this as your normal (administrator) user."
    if [ "$(uname -m)" = arm64 ]; then
      say "Installing Homebrew"
      brew_installer="$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" \
        || die "Could not download the Homebrew installer (no network?)"
      # NONINTERACTIVE: the installer would wait for RETURN. sudo is already unlocked above, so it asks nothing.
      NONINTERACTIVE=1 /bin/bash -c "$brew_installer" \
        || die "The Homebrew installer failed (its output is above). Fix that, then run this again."
    else
      say "Installing Homebrew for an Intel Mac (its own installer no longer supports Intel, so: git checkout)"
      brew_install_intel
    fi
  fi
  # a Homebrew from an earlier run may sit in directories that root owns
  [ "$(uname -m)" = arm64 ] || brew_fix_intel_dirs
  [ -x "$brew_bin" ] || die "Homebrew is not at $brew_bin after installing it (the installer output above says why)"
  # PATH for everything started from here on: chezmoi and every script it runs
  eval "$("$brew_bin" shellenv)"
  say "Homebrew: $(brew --version | sed -n 1p) ($brew_bin)"
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
# DOTFILES_CHEZMOI_VERSION=v2.73.2 pins the release; the installer takes the tag with -t
sh -c "$(curl -fsLS get.chezmoi.io)" -- -b "$CHEZMOI_TMP" ${DOTFILES_CHEZMOI_VERSION:+-t "$DOTFILES_CHEZMOI_VERSION"}
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

# 4. everything else
# Extra chezmoi flags, e.g. DOTFILES_CHEZMOI_ARGS="--verbose" (CI uses it for a readable log)
extra=()
if [ -n "${DOTFILES_CHEZMOI_ARGS:-}" ]; then read -r -a extra <<< "$DOTFILES_CHEZMOI_ARGS"; fi

# ${extra[@]+...}: macOS bash 3.2 treats an empty array as unset under `set -u`
if [ -n "$SOURCE" ]; then
  say "chezmoi init --apply (from $SOURCE)"
  with_tty chezmoi init --source "$SOURCE" --apply ${extra[@]+"${extra[@]}"}
elif [ -n "$BRANCH" ]; then
  say "chezmoi init --apply $REPO (branch $BRANCH)"
  with_tty chezmoi init --apply --branch "$BRANCH" ${extra[@]+"${extra[@]}"} "$REPO"
else
  say "chezmoi init --apply $REPO"
  with_tty chezmoi init --apply ${extra[@]+"${extra[@]}"} "$REPO"
fi

say "Done. Open a new terminal."
