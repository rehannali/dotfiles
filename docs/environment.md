# Environment variables

Every variable the dotfiles read, grouped by what you are trying to do. The details of each one are in the page
linked next to it; this page is the index.

Three things to know first:

- **Nothing is required.** Anything you leave out is asked once on your terminal (the four questions) or has a
  default (install everything this Mac can run).
- **Where they are read.** The four *answers* (`DOTFILES_NAME`, `DOTFILES_EMAIL`, `DOTFILES_PROFILE`,
  `DOTFILES_BITWARDEN`) are read by `chezmoi init`, which stores them in `~/.config/chezmoi/chezmoi.toml`; after
  that the variable is no longer needed. Everything else is read by the install scripts **each time they run**,
  and is never stored.
- **Where to put them.** In front of the command (`DOTFILES_CASKS=check bash bootstrap.sh`) or exported for the
  session. `bootstrap.sh` has a flag for most of them (`bootstrap.sh --help`). Do not put passwords or tokens in
  your shell profile.

## What do you want to do?

| Scenario | Set | Where it is explained |
|---|---|---|
| First install on my own Mac, answering questions | nothing | [README](../README.md) |
| No questions at all (fresh VM, script, CI) | `DOTFILES_NAME`, `DOTFILES_EMAIL`, `DOTFILES_PROFILE`, `DOTFILES_BITWARDEN=false`, plus `DOTFILES_XCODE=skip` and `DOTFILES_MAS=skip` | [configuration.md](configuration.md) |
| A server, no GUI apps | `DOTFILES_PROFILE=cli` (`--cli`) | [README](../README.md) |
| Try it without installing the ~70 apps | `DOTFILES_CASKS=check` (`--no-casks`) | [configuration.md](configuration.md) |
| Skip Xcode (needs an Apple ID and a code) | `DOTFILES_XCODE=skip` (`--no-xcode`) | [configuration.md](configuration.md) |
| Install Xcode but not the simulator runtime | `DOTFILES_RUNTIME=skip` | [configuration.md](configuration.md) |
| A specific Xcode / runtime, not the newest this Mac can run | `DOTFILES_XCODE_VERSION=26.6`, `DOTFILES_IOS_RUNTIME=26.5` (`--xcode`, `--ios-runtime`) | [configuration.md](configuration.md) |
| Xcode without typing the Apple ID | `XCODES_USERNAME` and `XCODES_PASSWORD`, or the Bitwarden item `Apple ID` | [bitwarden.md](bitwarden.md) |
| Xcode without the two-factor code | `FASTLANE_SESSION` (a saved Apple session, valid about a month) | [bitwarden.md](bitwarden.md), [ci.md](ci.md) |
| Xcode without any Apple login | `DOTFILES_XCODE_XIP=/path/Xcode_26.6.xip` (a download you made yourself) | [configuration.md](configuration.md) |
| No Mac App Store apps (App Store not signed in) | `DOTFILES_MAS=skip` (`--no-appstore`) | [configuration.md](configuration.md) |
| No Flutter SDK | `DOTFILES_FLUTTER=skip` (`--no-flutter`) | [configuration.md](configuration.md) |
| Secrets from Bitwarden | `DOTFILES_BITWARDEN=true` (`--bitwarden`) | [bitwarden.md](bitwarden.md) |
| Bitwarden, my own machine (API key) | `BW_CLIENTID`, `BW_CLIENTSECRET`, optionally `BW_PASSWORD` | [bitwarden.md](bitwarden.md) |
| Bitwarden, work machine (SSO) | `DOTFILES_BW_METHOD=sso` (`--bw-method sso`) | [bitwarden.md](bitwarden.md) |
| Bitwarden, email and master password | `DOTFILES_BW_EMAIL` (`--bw-email`, defaults to `DOTFILES_EMAIL`), optionally `BW_PASSWORD` | [bitwarden.md](bitwarden.md) |
| Bitwarden on a self-hosted or EU server (custom URL) | `DOTFILES_BW_SERVER=https://vault.example.com` (`--bw-server`), together with any login method above | [bitwarden.md](bitwarden.md) |
| Bitwarden on a self-hosted server **and** an API key | `DOTFILES_BW_SERVER`, `BW_CLIENTID`, `BW_CLIENTSECRET` (and `BW_PASSWORD`) | [bitwarden.md](bitwarden.md) |
| Vault already unlocked in this shell | `BW_SESSION` (what `bw unlock --raw` prints) | [bitwarden.md](bitwarden.md) |
| Test a branch or a fork | `--branch NAME`, `DOTFILES_REPO=owner/name` | [configuration.md](configuration.md) |
| Test an uncommitted local checkout | `DOTFILES_SOURCE=/path` (`--source`) | [configuration.md](configuration.md) |
| See everything chezmoi does | `DOTFILES_CHEZMOI_ARGS=--verbose` | [configuration.md](configuration.md) |
| Same chezmoi version on every machine | `DOTFILES_CHEZMOI_VERSION=v2.73.2` | [configuration.md](configuration.md) |
| Keep my Dock, Finder and trackpad settings | `DOTFILES_DEFAULTS=skip` (`--no-defaults`), or `settings.macos.defaults = false` | [configuration.md](configuration.md) |
| Don't change my login shell (no `sudo chsh`) | `DOTFILES_CHSH=skip` (`--no-chsh`) | [configuration.md](configuration.md) |
| My own extra environment variables or PATH entries | not a variable: `settings.shell.env` / `settings.shell.path` | [configuration.md](configuration.md) |
| Change fonts, theme, git settings, Flutter version | not variables: the `settings` in `chezmoi.toml` | [configuration.md](configuration.md) |

Examples:

```sh
# no questions, no Xcode, no App Store, personal Mac
DOTFILES_NAME="Ada Lovelace" DOTFILES_EMAIL=ada@example.com DOTFILES_PROFILE=full DOTFILES_BITWARDEN=false \
  bash bootstrap.sh --no-xcode --no-appstore

# server
bash bootstrap.sh --cli --name "Ada Lovelace" --email ada@example.com

# a specific Xcode, Apple ID from the environment for this one command
XCODES_USERNAME=ada@example.com XCODES_PASSWORD='...' bash bootstrap.sh --xcode 26.6
```

## Reference

### The four answers (read by `chezmoi init`, then stored)

| Variable | Values | Notes |
|---|---|---|
| `DOTFILES_NAME` | your full name | git commit name. A machine that never answered gets `chezmoi: no name for git: run chezmoi init again` |
| `DOTFILES_EMAIL` | your email | git commit email. Also the default Bitwarden login |
| `DOTFILES_PROFILE` | `full` (default), `cli` | `cli` = command-line tools and terminal setup only: no casks, App Store apps, Xcode or GUI configs |
| `DOTFILES_BITWARDEN` | `true`, `false` | `true` also sets `[bitwarden] unlock = "auto"` in `chezmoi.toml` |

A variable that is set wins over the stored answer when `chezmoi init` is run again.

### Switches for one run (read by the scripts, never stored)

| Variable | Values | Read by | Effect |
|---|---|---|---|
| `DOTFILES_XCODE` | `skip` | pre-setup, runtime script | no Xcode, no simulator runtime |
| `DOTFILES_XCODE_VERSION` | e.g. `26.6` | pre-setup | this Xcode instead of the newest this Mac can run |
| `DOTFILES_IOS_RUNTIME` | e.g. `26.5` | runtime script | this runtime instead of the one that goes with the Xcode |
| `DOTFILES_RUNTIME` | `skip` | runtime script | Xcode yes, simulator runtime no |
| `DOTFILES_XCODE_XIP` | path to a `.xip` | pre-setup | install that file, no Apple login |
| `DOTFILES_FLUTTER` | `skip` | Flutter script | no Flutter SDK |
| `DOTFILES_DEFAULTS` | `skip` | macOS defaults script | leave the Dock, Finder and trackpad settings alone |
| `DOTFILES_CHSH` | `skip` | change-shell script | do not make zsh the login shell |
| `DOTFILES_CASKS` | `install` (default), `check`, `skip` | package script | `check` verifies each cask can be installed here and installs none |
| `DOTFILES_MAS` | `install` (default), `skip` | package script | no App Store apps |
| `DOTFILES_SKIP_CASKS` | space separated cask names | package script | leave these casks out of this run |
| `DOTFILES_MACPORTS` | `install` (default), `skip` | package script, Intel Macs | `skip`: no MacPorts fallback for tools without a Homebrew bottle |
| `DOTFILES_REPO` | `owner/name` | `bootstrap.sh` | repo to apply, default `rehannali/dotfiles` |
| `DOTFILES_SOURCE` | path | `bootstrap.sh` | local checkout instead of GitHub |
| `DOTFILES_CHEZMOI_ARGS` | e.g. `--verbose` | `bootstrap.sh` | extra flags for `chezmoi init` |
| `DOTFILES_CHEZMOI_VERSION` | a release tag, e.g. `v2.73.2` | `bootstrap.sh` | download that chezmoi instead of the latest |

### When a change takes effect

chezmoi remembers which scripts it has run. The pre-setup script (Homebrew, Xcode), the oh-my-zsh and zsh theme
scripts, the global npm packages and iTerm2 integration script, the simulator runtime script and the login shell
script run **once per machine**; the package, apt, mise, Ruby gem, Flutter and macOS defaults scripts run again
whenever their rendered content changes (for example after you add a tool to `packages.yml`, or change a dock
setting). So setting
`DOTFILES_XCODE_VERSION` on a Mac that has already finished its first run does nothing by itself. To run the
once-only scripts again:

```sh
chezmoi state delete-bucket --bucket=scriptState
chezmoi apply
```

That re-runs every script, which is safe (each one skips what is already installed) but not quick.

### Credentials

| Variable | Used for | Notes |
|---|---|---|
| `XCODES_USERNAME`, `XCODES_PASSWORD` | Apple ID for `xcodes` | otherwise the Bitwarden item named in `settings.apple.bitwarden_item`, otherwise `xcodes` asks |
| `FASTLANE_SESSION` | Apple login without the two-factor code | used with `xcodes --use-fastlane-auth`. Make one with `fastlane spaceauth` or the `apple-session` workflow |
| `BW_CLIENTID`, `BW_CLIENTSECRET` | Bitwarden API key login | both set means `DOTFILES_BW_METHOD=apikey` is picked automatically |
| `BW_PASSWORD` | master password, so it is not asked | export for one command only |
| `BW_SESSION` | an unlocked vault | `bootstrap.sh` sets it and passes it on to chezmoi |
| `DOTFILES_BW_METHOD` | `apikey`, `sso`, `password` | default: `apikey` if the two API variables are set, else `password` |
| `DOTFILES_BW_EMAIL` | Bitwarden login email | default `DOTFILES_EMAIL`, else asked |
| `DOTFILES_BW_SERVER` | self-hosted or EU server URL, e.g. `https://vault.example.com` or `https://vault.bitwarden.eu` | `bootstrap.sh` runs `bw config server` with it before logging in, for every method (API key, SSO, password). Only applied while logged out: if the CLI is already logged in to another server run `bw logout` first |

`bootstrap.sh` flags for the Bitwarden variables: `--bitwarden`, `--bw-method`, `--bw-email`, `--bw-server`; each
`--bw-*` flag also turns Bitwarden on. The secrets themselves (`BW_CLIENTID`, `BW_CLIENTSECRET`, `BW_PASSWORD`) have
no flag on purpose, so they do not end up in your shell history or in `ps`.

### Settings that are not environment variables

Fonts, themes, git options, the Flutter version, the Dock, extra variables and PATH entries, the WSL distribution
and the Bitwarden item for the Apple ID are values in `home/.chezmoidata/settings.yml`. Override them per machine
in `~/.config/chezmoi/chezmoi.toml` under `[data.settings...]`. The full list is in
[configuration.md](configuration.md#settings).

### GitHub Actions (this repo's own workflows)

Set in the repository settings, not in a shell. Details in [ci.md](ci.md).

| Name | Kind | Used by | Meaning |
|---|---|---|---|
| `APPLE_SESSION_USER` | variable | `apple-session`, `apple-session-check` | the only GitHub user who may start them and join the terminal |
| `UPTERM_SERVER`, `UPTERM_KNOWN_HOSTS` | variables | `apple-session` | your own upterm relay and its host key; leave unset for upterm's public relay |
| `FASTLANE_SESSION` | secret | `dotfiles` (only with `xcode=install`), `apple-session-check` | the saved Apple session; written by `get-session` |
| `SECRETS_WRITE_TOKEN` | secret of the `apple-session` environment | `apple-session` | fine-grained token (Secrets: read and write) that lets the runner save `FASTLANE_SESSION` |

`dotfiles.yml` sets the `DOTFILES_*` variables itself for each runner: name `CI`, the matrix profile,
`DOTFILES_BITWARDEN=false`, `DOTFILES_MAS=skip`, `DOTFILES_CASKS=check` for pull requests (what the manual
`casks` input selects otherwise), `DOTFILES_XCODE` and `DOTFILES_RUNTIME` only from the manual inputs, and
`DOTFILES_SOURCE` pointing at the checkout.

### Set by the scripts themselves

You should not need to set these. They are listed so you recognise them in logs.

| Variable | Set by | Why |
|---|---|---|
| `HOMEBREW_NO_ANALYTICS`, `HOMEBREW_NO_INSTALL_CLEANUP` | shared helper | quiet, and no cleanup in the middle of a run |
| `HOMEBREW_NO_AUTO_UPDATE`, `HOMEBREW_NO_INSTALL_UPGRADE`, `HOMEBREW_MAKE_JOBS=2` | helper, Intel Macs only | Intel is Homebrew Tier 3: never update, upgrade or compile on the side |
| `MISE_JOBS=2`, `MAKE_OPTS`, `RUBY_MAKE_OPTS` | mise script | keep compiling (Ruby, Rust crates on Intel) from filling the machine |
| `MISE_GITHUB_TOKEN`, `HOMEBREW_GITHUB_API_TOKEN` | `dotfiles.yml` | avoid anonymous GitHub API rate limits on runners |
| `FASTLANE_DONT_STORE_PASSWORD`, `FASTLANE_OPT_OUT_USAGE`, `FASTLANE_SKIP_UPDATE_CHECK` | `get-session`, `apple-session` | no keychain prompt, no analytics, no update nag |
| `SPACESHIP_*` | the zsh prompt config | prompt look and feel, not inputs; see the zsh files |

### Helper scripts

| Script | Options | What it reads |
|---|---|---|
| `scripts/check-install.py` | `--source PATH` (read the tool plan from a checkout instead of chezmoi's own), `--no-shell` (skip the interactive zsh check) | the audit expects what the run installed, so it reads the same `DOTFILES_PROFILE`, `DOTFILES_FLUTTER`, `DOTFILES_XCODE` and `DOTFILES_XCODE_VERSION`; set them the way you set them for the apply. Writes the summary to `$GITHUB_STEP_SUMMARY` in Actions |
| `scripts/verify-render.sh [OUTPUT_DIR]` | `VERIFY_TARGETS="linux/amd64 darwin/arm64/cli"` limits the targets (`os/arch[/profile]`) | needs `chezmoi`, `shellcheck`, `python3`, `zsh`; nothing is applied |
| `scripts/apple-session.sh APPLE_ID [--save]` | `--save` stores the session as the repository secret `FASTLANE_SESSION` with `gh` | sets `FASTLANE_OPT_OUT_USAGE` and `FASTLANE_SKIP_UPDATE_CHECK` itself; see [ci.md](ci.md) |
