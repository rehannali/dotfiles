# bootstrap.sh options and environment variables

What a machine gets is decided by the inventory (`ansible/inventory/`, see [configuration.md](configuration.md)).
These options and variables are for `bootstrap.sh`. Each turns into an `ansible-playbook -e ...`, so the same can be
done with `-e` when you run the playbook yourself.

The options that describe the machine (name, email, `--cli`, `--bitwarden`, the `--no-*` ones, `--xcode`, casks left
out) are kept in `~/.config/dotfiles/local.yml`, so later `dot apply` / `dot sync` runs use them too; see
[usage.md](usage.md#this-machines-choices). `--check`, `--branch`, `--source` and `DOTFILES_ANSIBLE_ARGS` are for the
one run.

Put variables in front of the command (`DOTFILES_CASKS=skip bash bootstrap.sh`) or export them for the session.
Do not put passwords or tokens in your shell profile.

## What do you want to do?

| Scenario | Set | Explained in |
|---|---|---|
| Set up this machine as listed in the inventory | `--host NAME` (default: the hostname) | [README](../README.md) |
| A Mac | `--home` (personal) or `--office` (work); its hostname is the host name, Intel / Apple Silicon is detected | [README](../README.md) |
| Another machine, not in the inventory | `--group servers` (or `linux_desktop`, `wsl`); `--host NAME` to name it other than its hostname; without `--group` it is asked, with a suggestion | [README](../README.md) |
| No questions at all (fresh VM, script, CI) | `--yes` (`DOTFILES_YES=true`): takes every suggestion; give `--name` / `--email` (or have them in the inventory or your git config), plus `--no-xcode --no-appstore` | [setup-guide.md](setup-guide.md#before-the-first-run) |
| A Linux desktop without Flathub / Snap apps | `DOTFILES_FLATPAKS=skip` (`--no-flatpaks`), `DOTFILES_SNAPS=skip` (`--no-snaps`) | [configuration.md](configuration.md) |
| A server, no GUI apps | put it in the `servers` group, or `--cli` for one run | [configuration.md](configuration.md) |
| See what would change, change nothing | `--check` | |
| Try it without installing the ~70 apps | `DOTFILES_CASKS=skip` (`--no-casks`) | [configuration.md](configuration.md) |
| Leave some casks out of this run | `DOTFILES_SKIP_CASKS="netbird-ui spotify"` | [configuration.md](configuration.md) |
| Skip Xcode (needs an Apple ID and a code) | `DOTFILES_XCODE=skip` (`--no-xcode`) | [configuration.md](configuration.md) |
| Install Xcode but not the simulator runtime | `DOTFILES_RUNTIME=skip` | [configuration.md](configuration.md) |
| A specific Xcode / runtime, not the newest this Mac can run | `DOTFILES_XCODE_VERSION=26.6`, `DOTFILES_IOS_RUNTIME=26.5` (`--xcode`, `--ios-runtime`) | [configuration.md](configuration.md) |
| Xcode without typing the Apple ID | `XCODES_USERNAME` and `XCODES_PASSWORD`, or the Bitwarden item `Apple ID` | [bitwarden.md](bitwarden.md) |
| Xcode without the two-factor code | `FASTLANE_SESSION` (a saved Apple session, valid about a month) | [bitwarden.md](bitwarden.md), [ci.md](ci.md) |
| Xcode without any Apple login | `DOTFILES_XCODE_XIP=/path/Xcode_26.6.xip` (a download you made yourself) | [configuration.md](configuration.md) |
| No Mac App Store apps (App Store not signed in) | `DOTFILES_MAS=skip` (`--no-appstore`) | [configuration.md](configuration.md) |
| No Flutter SDK | `DOTFILES_FLUTTER=skip` (`--no-flutter`) | [configuration.md](configuration.md) |
| Intel Mac without its MacPorts tools | `DOTFILES_MACPORTS=skip` (`--no-macports`) | [configuration.md](configuration.md) |
| Keep my Dock, Finder and trackpad settings | `DOTFILES_DEFAULTS=skip` (`--no-defaults`), or `macos_defaults: false` in the inventory | [configuration.md](configuration.md) |
| Don't change my login shell | `DOTFILES_CHSH=skip` (`--no-chsh`), or `login_shell_zsh: false` | [configuration.md](configuration.md) |
| Secrets from Bitwarden | `DOTFILES_BITWARDEN=true` (`--bitwarden`), or `bitwarden: true` | [bitwarden.md](bitwarden.md) |
| Bitwarden, my own machine (API key) | `BW_CLIENTID`, `BW_CLIENTSECRET`, optionally `BW_PASSWORD` | [bitwarden.md](bitwarden.md) |
| Bitwarden, work machine (SSO) | `DOTFILES_BW_METHOD=sso` (`--bw-method sso`) | [bitwarden.md](bitwarden.md) |
| Bitwarden, email and master password | `DOTFILES_BW_EMAIL` (`--bw-email`, defaults to `--email`), optionally `BW_PASSWORD` | [bitwarden.md](bitwarden.md) |
| Bitwarden on a self-hosted or EU server | `DOTFILES_BW_SERVER=https://vault.example.com` (`--bw-server`), with any login method above | [bitwarden.md](bitwarden.md) |
| Vault already unlocked in this shell | `BW_SESSION` (what `bw unlock --raw` prints) | [bitwarden.md](bitwarden.md) |
| Nobody at the keyboard to type the sudo password (CI, a self-hosted runner, a script) | `DOTFILES_SUDO_PASSWORD`, and `DOTFILES_BECOME_PASSWORD` only if Ansible's differs | |
| Test a branch or a fork | `--branch NAME`, `DOTFILES_REPO=owner/name` | |
| Test an uncommitted local checkout | `DOTFILES_SOURCE=/path` (`--source`); it is used as it is, never pulled | |
| Only one part (e.g. the dotfiles) | `DOTFILES_ANSIBLE_ARGS="--tags dotfiles"` | [README](../README.md) |
| Fewer / more retries | `DOTFILES_ANSIBLE_ARGS="-e install_retries=5"`, or `install_retries` in the inventory | [configuration.md](configuration.md) |

Examples:

```sh
# no questions, no Xcode, no App Store, a personal Mac
bash bootstrap.sh --home --name "Ada Lovelace" --email ada@example.com --no-xcode --no-appstore

# a server that is not in the inventory yet
bash bootstrap.sh --host pi --group servers --name "Ada Lovelace" --email ada@example.com

# a specific Xcode, Apple ID from the environment for this one command
XCODES_USERNAME=ada@example.com XCODES_PASSWORD='...' bash bootstrap.sh --home --xcode 26.6
```

## Reference

### Options and their variables

| Option | Variable | Becomes |
|---|---|---|
| `--host NAME` | `DOTFILES_HOST` | `-l NAME`; default the hostname |
| `--home`, `--office` | `DOTFILES_GROUP=home` / `office` | a Mac: `mac_personal` / `mac_work` |
| `--group GROUP` | `DOTFILES_GROUP` | a machine not in the inventory is put in GROUP for this run (default `mac_personal` on a Mac, `servers` on Linux) |
| `--name`, `--email` | `DOTFILES_NAME`, `DOTFILES_EMAIL` | `git_name`, `git_email` |
| `--cli` | `DOTFILES_PROFILE=cli` | `gui_apps=false` |
| `--bitwarden` | `DOTFILES_BITWARDEN=true` | logs in / unlocks Bitwarden first, then `bitwarden=true` |
| `--no-xcode` | `DOTFILES_XCODE=skip` | `install_xcode=false`, `install_ios_runtime=false` |
| | `DOTFILES_RUNTIME=skip` | `install_ios_runtime=false` |
| `--xcode V`, `--ios-runtime V` | `DOTFILES_XCODE_VERSION`, `DOTFILES_IOS_RUNTIME` | `xcode_version`, `ios_runtime` |
| | `DOTFILES_XCODE_XIP` | read by the xcode role: install that `.xip`, no Apple login |
| `--no-flutter` | `DOTFILES_FLUTTER=skip` | `install_flutter=false` |
| `--no-casks` | `DOTFILES_CASKS=skip` | `install_casks=false` |
| | `DOTFILES_SKIP_CASKS` | `apps_skip`: apps (by name in packages.yml) left out of this run |
| `--no-appstore` | `DOTFILES_MAS=skip` | `install_app_store=false` |
| `--no-macports` | `DOTFILES_MACPORTS=skip` | `macports_fallback=false` |
| `--no-defaults` | `DOTFILES_DEFAULTS=skip` | `macos_defaults=false` |
| `--no-chsh` | `DOTFILES_CHSH=skip` | `login_shell_zsh=false` |
| `--no-flatpaks` | `DOTFILES_FLATPAKS=skip` | `install_flatpaks=false` |
| `--no-snaps` | `DOTFILES_SNAPS=skip` | `install_snaps=false` |
| `--yes`, `-y` | `DOTFILES_YES=true` | asks nothing: the suggested group, the name / email from your git config; no summary to confirm (also read by `dot`) |
| `--check` | | `--check --diff` |
| `--branch NAME` | | clone / update that branch |
| `--source PATH` | `DOTFILES_SOURCE` | use that checkout (`dotfiles_update=false`) |
| | `DOTFILES_REPO` | `owner/name` to clone, default `rehannali/dotfiles` |
| | `DOTFILES_DIR` | where the repo is (cloned there if missing); default: the checkout `bootstrap.sh` runs from, else `~/.dotfiles` |
| | `DOTFILES_ANSIBLE_ARGS` | more `ansible-playbook` options, word-split |

### Credentials

| Variable | Used for | Notes |
|---|---|---|
| `XCODES_USERNAME`, `XCODES_PASSWORD` | Apple ID for `xcodes` | otherwise the Bitwarden item named in `settings.apple.bitwarden_item` (when Bitwarden is on), otherwise `xcodes` asks on the terminal step |
| `FASTLANE_SESSION` | Apple login without the two-factor code | used with `xcodes --use-fastlane-auth`. Make one with `fastlane spaceauth` or the `apple-session` workflow |
| `BW_CLIENTID`, `BW_CLIENTSECRET` | Bitwarden API key login | both set means `DOTFILES_BW_METHOD=apikey` is picked automatically, and Bitwarden is on (as `--bitwarden`) |
| `BW_PASSWORD` | master password, so it is not asked | export for one command only; also unlocks the vault for a plain `ansible-playbook` run |
| `DOTFILES_SUDO_PASSWORD` | sudo's password, so it is not asked | `bootstrap.sh` and `dot` unlock sudo with it (`sudo -S`) and hand it to Ansible as the become password through a script that prints it (`--become-password-file`), so it is never written to a file. Every process of the run inherits it: export it for one command only, or set it as a CI secret |
| `DOTFILES_BECOME_PASSWORD` | Ansible's become password, when it is not the sudo password | default `DOTFILES_SUDO_PASSWORD` |
| `BW_SESSION` | an unlocked vault | `bootstrap.sh` sets it; the playbook's Bitwarden lookups use it |
| `DOTFILES_BW_METHOD` | `apikey`, `sso`, `password` | default: `apikey` if the two API variables are set, else `password` |
| `DOTFILES_BW_EMAIL` | Bitwarden login email | default `--email`, else asked |
| `DOTFILES_ENV_FILE` | a path | your environment variables without Bitwarden, default `~/.config/dotfiles/env` (`ansible/env.example`) |
| `DOTFILES_BW_REMEMBER` | `false` | keep nothing: by default the API key and master password go to the Keychain / Secret Service after the first setup, so `bw`, `dot` and later runs unlock by themselves |
| `DOTFILES_BW_SERVER` | self-hosted or EU server URL | `bootstrap.sh` runs `bw config server` with it before logging in. Only applied while logged out: if the CLI is already logged in to another server run `bw logout` first |

The secrets themselves (`BW_CLIENTID`, `BW_CLIENTSECRET`, `BW_PASSWORD`) have no option on purpose, so they do not
end up in your shell history or in `ps`.

### GitHub Actions (this repo's own workflows)

Set in the repository settings, not in a shell. Details in [ci.md](ci.md).

| Name | Kind | Used by | Meaning |
|---|---|---|---|
| `APPLE_SESSION_USER` | variable | `apple-session`, `apple-session-check` | the only GitHub user who may start them and join the terminal |
| `UPTERM_SERVER`, `UPTERM_KNOWN_HOSTS` | variables | `apple-session` | your own upterm relay and its host key; leave unset for upterm's public relay |
| `FASTLANE_SESSION` | secret | `dotfiles` (only with `xcode=install`), `apple-session-check` | the saved Apple session; written by `get-session` |
| `SECRETS_WRITE_TOKEN` | secret of the `apple-session` environment | `apple-session` | fine-grained token (Secrets: read and write) that lets the runner save `FASTLANE_SESSION` |

`dotfiles.yml` sets the variables itself for each runner: `--host ci --group <servers or mac_personal>`, name `CI`,
`DOTFILES_BITWARDEN=false`, `DOTFILES_MAS=skip`, `DOTFILES_CASKS=skip` for pull requests (what the manual `casks`
input selects otherwise), `DOTFILES_XCODE` and `DOTFILES_RUNTIME` only from the manual inputs, and `DOTFILES_SOURCE`
pointing at the checkout.

### Set by the playbook itself

You should not need to set these. They are listed so you recognise them in logs.

| Variable | Set by | Why |
|---|---|---|
| `HOMEBREW_NO_ANALYTICS`, `HOMEBREW_NO_INSTALL_CLEANUP` | packages role | quiet, and no cleanup in the middle of a run |
| `HOMEBREW_NO_AUTO_UPDATE`, `HOMEBREW_NO_INSTALL_UPGRADE`, `HOMEBREW_MAKE_JOBS=2` | packages role, Intel Macs only | Intel is Homebrew Tier 3: never update, upgrade or compile on the side |
| `MISE_JOBS=2`, `MAKE_OPTS`, `RUBY_MAKE_OPTS` | mise role | keep compiling (Ruby, Rust crates on Intel) from filling the machine |
| `MISE_GITHUB_TOKEN`, `HOMEBREW_GITHUB_API_TOKEN` | `dotfiles.yml` | avoid anonymous GitHub API rate limits on runners |
| `FASTLANE_DONT_STORE_PASSWORD`, `FASTLANE_OPT_OUT_USAGE`, `FASTLANE_SKIP_UPDATE_CHECK` | `get-session`, `apple-session` | no keychain prompt, no analytics, no update nag |

### Helper scripts

| Script | Options | What it reads |
|---|---|---|
| `scripts/check-install.py` | `--plan FILE` (default `~/.cache/dotfiles/plan.json`, written by every run), `--no-shell` (skip the interactive zsh check) | the plan says what this machine should have; writes the summary to `$GITHUB_STEP_SUMMARY` in Actions |
| `ansible/tests/packages_check.py` | | `packages.yml`: one manager per tool, tap trust lists; needs ansible-core and PyYAML |
| `ansible/tests/apps_check.py` | `--markdown FILE` | every cask, App Store id, Flathub id, Homebrew formula and apt name, looked up in its store; needs PyYAML and the internet |
| `ansible/tests/render.yml` | `ansible-playbook -i localhost, -c local tests/render.yml` | renders every template for every kind of machine into a temp dir; changes nothing |
| `scripts/apple-session.sh APPLE_ID [--save]` | `--save` stores the session as the repository secret `FASTLANE_SESSION` with `gh` | see [ci.md](ci.md) |
