# Configuration

Everything you might want to change, and where. Nothing here needs a code change: it is all variables in
`ansible/inventory/`.

Looking for a `bootstrap.sh` option or an environment variable? [environment.md](environment.md) lists them all.

## Where a variable goes

| File | For |
|---|---|
| `inventory/hosts.yml` | which machines there are, and which group each is in |
| `inventory/group_vars/all/main.yml` | what every machine gets: name and email, the switches below, extra / skipped / removed packages |
| `inventory/group_vars/all/packages.yml` | every package any machine can get, in bundles |
| `inventory/group_vars/all/platforms.yml` | which package manager installs what on each OS (Apple Silicon, Intel Mac, Debian) |
| `inventory/group_vars/all/settings.yml` | matters of taste: git, terminal fonts and theme, Dock, shell variables, Flutter version |
| `inventory/group_vars/all/secrets.yml` | environment variables fetched from Bitwarden |
| `inventory/group_vars/all/toolchain.yml` | Xcode and simulator runtime version (empty = newest that fits) |
| `inventory/group_vars/<group>.yml` | what a kind of machine does differently (`mac_work`, `servers`, ...) |
| `inventory/host_vars/<host>.yml` | what one machine does differently |

A variable in a group or host file replaces the one in `all/`. That also goes for lists and dicts: they are
replaced, not merged. The one exception is `settings`: put only the keys you change in `settings_override`, and
they are merged into the defaults (a host's `settings_override` replaces its group's, though).

For a single run, `-e` beats everything: `ansible-playbook site.yml -l macbook -e install_casks=false`, or the
`bootstrap.sh` options.

## Name and email

`git_name` and `git_email` in `main.yml` (or per group, e.g. a work email in `group_vars/mac_work.yml`). They go
into `~/.gitconfig`. `bootstrap.sh --name/--email` sets them for this machine (kept in
`~/.config/dotfiles/local.yml`), and when nothing sets them the first run asks. A run without them writes no
dotfiles and says so.

## Switches

All in `main.yml`, `true` unless noted:

| Switch | Effect |
|---|---|
| `gui_apps` | `false`: command-line tools and the terminal setup only. No casks, no App Store apps, no Xcode, no Flutter, no macOS defaults, no alacritty / wezterm / karabiner / hyper configs, no `apple` tools. The `servers` and `wsl` groups set it |
| `install_casks` | macOS GUI apps (Homebrew casks) |
| `install_flatpaks` | Linux GUI apps from Flathub (machines with `gui_apps`, e.g. the `linux_desktop` group) |
| `install_app_store` | Mac App Store apps (needs an App Store that is signed in). `mac_work` sets it to `false` |
| `macports_fallback` | Intel Mac: MacPorts for formulae Homebrew has no bottle for |
| `macos_defaults` | the Dock (from `settings.macos.dock`), Finder and trackpad preferences |
| `touch_id_sudo` | macOS 14+ with a Touch ID sensor: `sudo` asks for your fingerprint. Writes `/etc/pam.d/sudo_local` (survives macOS updates), with `pam_reattach` for tmux when `brew install pam-reattach` was done. A `sudo_local` that was not written by these dotfiles is left alone. Undo with `sudo rm /etc/pam.d/sudo_local` |
| `install_xcode`, `install_ios_runtime` | Xcode and the iOS simulator runtime, see "Xcode" below |
| `install_flutter` | Flutter with fvm, version from `settings.flutter.version` |
| `login_shell_zsh` | make zsh (Homebrew's or MacPorts' when there is one) the login shell |
| `bitwarden` | `false` by default: fetch `secrets.yml` (and the Apple ID) from Bitwarden, see [bitwarden.md](bitwarden.md) |
| `install_retries`, `install_delay` | `3` tries, `10` seconds apart, for every install and download |
| `dotfiles_dir` | where the repo lives on the machine, `~/.dotfiles` |

## Packages per kind of machine: bundles

`packages.yml` holds everything, grouped in **bundles**. A kind of machine says which bundles it gets in its group
file; nothing else reaches it:

| bundle | what |
|---|---|
| `core` | the shell and everyday command-line tools (zsh, git, tmux, neovim, bat, eza, zoxide, atuin, btop, gh, glab, rclone, ...) |
| `runtimes` | node, python, ruby, java, go, rust, uv from mise, and the global npm packages |
| `dev` | building software: docker, cmake, act, mkcert, poetry, zig, fvm, graphite (`gt`), ansible, compilers and headers |
| `media` | ffmpeg, imagemagick, graphicsmagick, ghostscript |
| `network` | nmap, aria2, wireguard-tools, openconnect, speedtest, unbound, telnet |
| `web` | nginx, php |
| `mac_dev` | Apple development: xcodes, swiftlint, carthage, ios-deploy, ideviceinstaller, fastlane / cocoapods, Xcode extensions |
| `fonts` | the nerd fonts the terminal configs use (macOS) |
| `apps_dev` | terminals, editors, git clients, API and device tools |
| `apps_productivity` | browsers, office, notes, passwords, file sharing, small Mac utilities (Clop, MacPacker, Mole, Handy, ...): what a work machine needs too |
| `apps_network` | VPNs, firewalls, remote networks |
| `apps_personal` | music, video, chat, the rest of a personal machine |

| group | bundles |
|---|---|
| `mac_personal` | all of them |
| `mac_work` | core, runtimes, dev, mac_dev, fonts, apps_dev, apps_productivity (and no App Store) |
| `servers` (a Pi 4, a Hetzner VPS) | core, runtimes, dev |
| `wsl` | core, runtimes, dev |
| `linux_desktop` | core, runtimes, dev, media, network, apps_dev, apps_productivity, apps_personal (apps from Flathub) |

Change a group's list in `group_vars/<group>.yml`, or give one machine its own `bundles:` in `host_vars/<host>.yml`.
A new bundle is a new key under `bundles:` in `packages.yml`. For single packages on top of the bundles:

```yaml
# host_vars/office-mac.yml
tools_extra:
  - {name: awscli, kind: cli, mise: aws-cli, brew: awscli}
tools_skip: [ffmpeg]               # by `name`
apps_extra:
  - {name: slack, cask: slack, appdir: true, flatpak: com.slack.Slack}
apps_skip: [spotify, discord]      # by `name`
```

### Which manager installs what (platforms.yml)

Each entry in `packages.yml` names the package for every manager that has it; `platforms.yml` says, per platform,
which manager is used:

```yaml
platform_managers:
  macos_arm64: {cli: brew, system: brew, apps: [cask, mas]}
  macos_x86_64: {cli: brew, system: brew, apps: [cask, mas], fallbacks: false}   # mycask: bottle (Homebrew or CI); fallbacks: port, mise_fallback
  debian: {cli: mise, system: apt, apps: [flatpak]}            # Debian, Ubuntu, Raspberry Pi OS, WSL
```

- **Intel Macs after Homebrew:** Intel Macs already run without Homebrew: mycask installs their casks and formulae
  (`system: brew` names the formula), so this line stays as it is. To move a tool off Homebrew's bottles before
  September 2027, give it `intel_prefer: true` in `packages.yml`; [tools/mycask/README.md](../tools/mycask/README.md#timeline)
  has the timeline. `tests/packages_check.py` prints what would have no source once the bottles are gone.
- **Another Linux (Fedora, Arch, ...):** a machine whose platform is not in the table still gets the dotfiles, the
  shell and every mise tool and runtime; only the system packages are skipped, and the report says so. Supporting it
  fully means a `dnf:` / `pacman:` name on the system entries, a platform line here, and its install task in the
  packages role.
- **Linux GUI apps:** an app reaches a Linux desktop when it has a `flatpak` id (Flathub). Apps without one (most
  Mac-only apps) are left out there.

### Removing packages

Deleting a line from a list only stops installing it; machines that have it keep it. To take something off
machines, list it under `remove` (in `main.yml` for every machine, or in a group / host file):

```yaml
remove:
  brew: [thefuck]
  cask: [kodi]
  mas: [1451685025]
  apt: [telnet]
  mise: [zig]          # also dropped from the mise config
  port: [ffmpeg]       # MacPorts, Intel Macs
  flatpak: [com.spotify.Client]
```

Exactly those are uninstalled, on every run; nothing else is touched. Look first with `--check --diff`.

## Settings

Defaults in `group_vars/all/settings.yml`. To change some for a group or one machine:

```yaml
# host_vars/macbook.yml
settings_override:
  git:
    sign_commits: true
    signing_key: ABCD1234EF567890
  terminal:
    font: JetBrainsMono Nerd Font
    font_size: 13
    alacritty_theme: dracula
```

| Setting | Default | Used for |
|---|---|---|
| `git.default_branch` | `main` | `init.defaultBranch` |
| `git.sign_commits` | `false` | `commit.gpgSign` |
| `git.signing_key` | empty | `user.signingKey` (GPG key id, or an SSH public key path) |
| `git.signing_format` | `openpgp` | `gpg.format`, `openpgp` or `ssh` |
| `git.gpg_program` | `gpg` | `gpg.program` |
| `git.commit_template` | `~/.gitmessage` | `commit.template`, a file path; empty for none. `home/.gitmessage` is a Conventional Commits template |
| `apple.bitwarden_item` | `Apple ID` | Bitwarden item with your Apple ID, used by `xcodes` when Bitwarden is on |
| `locale` | `en_US.UTF-8` | `LANG` |
| `macos.cask_appdir` | `~/Applications` | where casks with `appdir: true` install their app. `/Applications` puts every app in one place. Only applies to casks installed from now on |
| `macos.dock.orientation`, `.tile_size`, `.autohide`, `.show_recents` | `left`, `42`, `true`, `false` | the Dock preferences |
| `shell.env` | the two Python variables | extra environment variables for every zsh (`~/.zshenv`), a map `NAME: value`; values may use `$HOME` |
| `shell.path` | empty | extra directories in front of `PATH`, first entry wins, for example `["$HOME/go/bin"]` |
| `wsl.distribution`, `.username` | `Ubuntu`, empty | the WSL domain wezterm offers on Windows; without a username wezterm uses the distribution's default user |
| `flutter.version` | `stable` | Flutter SDK that fvm installs and makes global (`stable`, `beta`, `3.35.0`...) |
| `terminal.font` | `Hack Nerd Font Mono` | alacritty and wezterm |
| `terminal.font_size` | `14` | alacritty, and wezterm on macOS |
| `terminal.font_size_other` | `11` | wezterm on Linux and Windows |
| `terminal.alacritty_theme` | `blood_moon` | file name from [alacritty-theme](https://github.com/alacritty/alacritty-theme) |

Flutter lands in `~/fvm/default` (a link to `~/fvm/versions/<version>`), and `~/fvm/default/bin` is on PATH, so
`flutter` and `dart` work in every shell and in IDEs. To use another version in one project: `fvm use 3.32.0`.
Android Studio and the Android SDK are not installed; Flutter needs them for Android builds.

## The dotfiles (home/)

`home/` is laid out exactly like your home directory:

- a plain file is **linked** from `~/.dotfiles/home/...`, so editing `~/.zshrc` edits the checkout. Commit and
  push from `~/.dotfiles`; other machines pick it up on their next run.
- a `.j2` file is a template (Jinja): it needs a setting, your name, or the OS. It is written without the `.j2`.
  Edit it in the repo, then run `--tags dotfiles`.
- a `.keep` file only makes sure its directory exists.

A file that is in the way of a link (a different file, not a link) is moved to `~/.dotfiles-backup/<time>/`
first. Copied instead of linked (`dotfiles_copy` in the dotfiles role): karabiner's config, because the app replaces
the file when it saves. Left off machines without `gui_apps`: alacritty, wezterm, karabiner, hyper; karabiner and
hyper also off Linux. One machine can leave more out with `dotfiles_skip_extra: [.config/btop]`.

Coding agents (`dotfiles_agents` in the dotfiles role): Claude Code (`~/.claude/CLAUDE.md`) and Codex
(`~/.codex/AGENTS.md`) get the same instructions for every project, written from
`roles/dotfiles/templates/agent-instructions.md.j2`: work as you in git, on GitHub (`gh`) and GitLab (`glab`), never
sign or mention themselves in commits, PRs or MRs, Conventional Commits by default (simple, subsystem prefix, gitmoji
and short styles when you ask for them). `home/.claude/settings.json` also turns off Claude Code's own attribution.
Codex has no such setting (it follows your ChatGPT account), so the global git hooks in `home/.config/git/hooks`
(`core.hooksPath`) drop AI co-author trailers and "Generated with ..." lines from every commit message; each hook
then runs the repository's own hook of the same name. A repository with its own `core.hooksPath` (husky) skips them.

Not parameterised: the hyper config, the Sourcetree diff/merge tool entries in the gitconfig, the tmux, neovim,
atuin, btop and karabiner settings, the Spaceship prompt (`home/.config/spaceship`) and the trackpad and Finder
preferences (`macos_defaults_list` in `roles/macos/defaults/main.yml`). They are plain files you edit. (The neovim
Lua modules are called `totu`, the author's handle; renaming the folder `lua/totu` and the five `require` / `import`
lines in `init.lua`, `lua/totu/lazy.lua` and `lua/totu/core/init.lua` is all it takes.)

### Zsh plugins, the prompt and the alacritty themes

- Oh My Zsh and its extra plugins (`zsh-autosuggestions`, `fast-syntax-highlighting`, `zsh-autocomplete`,
  `zsh-lsd`, `zsh-bat`, `you-should-use`, the Spaceship prompt, tmux's `tpm`, ...) are git clones listed in
  `roles/shell/defaults/main.yml`, updated on every run. The plugin names zsh loads are in `home/.zsh/omz.zsh`;
  plugins that wrap a command (`poetry`, `lsd`, `bat`, `thefuck`) are only loaded when that command exists. To add
  a plugin, add the clone to `shell_omz_plugins` and its name to `omz.zsh`.
- The Spaceship prompt is configured in `home/.config/spaceship/spaceship.zsh`.
- The alacritty themes are one archive pinned to a commit (`dotfiles_alacritty_theme_commit` in the dotfiles
  role); change the SHA to update. Not on machines without `gui_apps`.

## Xcode and the iOS runtime

Unless you say otherwise, the newest Xcode release **that this Mac can run** is installed, so two machines can end
up with different versions: an Intel Mac stops at an older Xcode than an Apple Silicon one, and a Mac on an older
macOS gets an older Xcode too. Betas and release candidates are never picked. It is worked out from the
[xcodereleases.com](https://xcodereleases.com) data (required macOS, supported CPUs) by `roles/xcode/files/xcode-pick.py`,
because `xcodes install --latest` only warns when the newest Xcode is too new for the Mac and then installs it anyway.

`xcodes` has its own idea of what suits a Mac, and the pick follows it: `xcodes list` shows only `[Universal]` builds on
an Intel Mac and only `[Apple Silicon]` builds on an Apple Silicon one, which is why an Intel Mac stops at the last
universal Xcode. You can look at it yourself:

```sh
xcodes list                                          # what this Mac is offered
xcodes list --architecture universal                 # Intel-compatible builds
xcodes list --architecture appleSilicon              # arm64-only builds
xcodes list --architecture x86_64                    # Intel-only builds
```

The iOS simulator runtime defaults to the one that belongs to the selected Xcode.

To pin a version, in order of priority:

1. `-e xcode_version=26.6 -e ios_runtime=26.5` for one run; `bootstrap.sh --xcode 26.6 --ios-runtime 26.5` keeps them
   for this machine (`~/.config/dotfiles/local.yml`)
2. `toolchain:` in `host_vars/<host>.yml` for one machine (both keys)
3. `group_vars/all/toolchain.yml` for every machine (both are empty there)

Signing in: Ansible can't type Apple's two-factor code. With a saved fastlane session (`FASTLANE_SESSION`, or the
custom field of that name on the Bitwarden item) or a `.xip` you downloaded (`DOTFILES_XCODE_XIP`) the run installs
Xcode itself. Otherwise it writes the command to `~/.cache/dotfiles/xcode-install.sh`, and `bootstrap.sh` runs that at
the end on your terminal (or run it yourself). The runtime is optional: if it can't be installed the run says so and
carries on; open Xcode once and add it under Settings, Components.

## packages.yml

Each bundle has `tools`, `apps`, `runtimes`, `npm` and / or `gems`. One entry per tool, with the name each package
manager uses. Leave a key out where the tool isn't available from that manager.

```yaml
- {name: bat, kind: cli, mise: bat, brew: bat, apt: bat}
```

| Key | Meaning |
|---|---|
| `name` | what the log calls it (and what `tools_skip` matches) |
| `kind` | `cli`: a single-binary tool mise can install; `system`: libraries, daemons, big apps (Homebrew or apt); `apple`: Apple developer tools, macOS only and not without `gui_apps` |
| `mise`, `brew`, `apt` | the package name for that manager |
| `bin` | the command the tool provides, when it differs from `name` (the CI check looks for it) |
| `port` | MacPorts port, used on Intel Macs only, when Homebrew has no bottle for the tool (also instead of compiling a `mise_intel: false` tool). Set it only if `packages.macports.org/<port>/` has a `darwin_25.x86_64` archive |
| `port_build` | `true`: MacPorts may compile the port itself when it has no binary archive (nmap has none, for its licence), but only once every dependency came from an archive, so it is minutes, never a chain of builds |
| `mise_fallback` | mise tool id, used on Intel Macs only, when Homebrew has no bottle and MacPorts (no `port`, or its install failed) cannot install the tool either. It goes into the mise config. `conda:<package>` installs conda-forge's prebuilt build (ffmpeg, imagemagick, ghostscript: MacPorts would compile their libpng and everything above it) |
| `mise_intel` | tool has no Intel Mac build in mise. A mise id (`"cargo:atuin"`) means Intel installs that instead, `false` means Intel uses Homebrew |
| `brew_service` | `true`: started with `brew services` once Homebrew installed it (nginx). Not when it came from MacPorts or mise instead; apt starts its own services |
| `prebuilt` | a tap formula that downloads a ready-made binary (so there is no bottle to look for) |

List what you want, not what it needs. When another listed package already installs a package as a runtime
dependency with the same manager on the same machine (Homebrew installs `libyaml` with `ansible`, apt installs
`git` with `git-flow`), the entry is left out or loses that manager's key, with a comment saying where it comes
from. Only runtime dependencies count: a bottle or a prebuilt binary never installs build-only ones. Check a formula
with `brew deps --formula <name>` (runtime) and `brew deps --formula --include-build <name>`, and an apt package with
`apt-cache depends <name>`. Keep an entry when the dependent is not installed on some machine: Intel Macs have no
Homebrew bottle for most formulae, so something that comes with another package on Apple Silicon may be the only
copy there.

### Taps and trust

Homebrew 6 and newer load nothing from a tap you have not trusted ([Tap Trust](https://docs.brew.sh/Tap-Trust)),
because a tap's formulae and casks are Ruby code that runs as you. Each tap under `taps:` lists what is used from
it:

```yaml
taps:
  - {name: xcodesorg/made, formulae: [xcodes]}
  - {name: netbirdio/tap, casks: [netbird-ui]}   # the app's cask is netbirdio/tap/netbird-ui
```

The packages role taps it and trusts the whole tap right away (`brew trust --tap xcodesorg/made`), before anything
is installed from it, so a cask that pulls in another formula of the same tap (netbird-ui needs netbird) works too.
A tap that can't be cloned or trusted is reported and the run goes on; on a Homebrew without `brew trust` nothing is
done. A formula or cask from a tap that is missing here makes `ansible/tests/packages_check.py` fail.

Before adding a new `cli` tool on every platform, check what mise has:

```sh
mise registry <tool>
mise lock --platform macos-x64,macos-arm64,linux-x64 <tool>    # run in an empty folder
```

A download URL for each platform is a good sign, not proof: one tool had a URL but the program ended up nowhere on
PATH. The CI check is what actually tells.

### Apps

```yaml
- {name: firefox, cask: firefox, appdir: true, flatpak: org.mozilla.firefox}
- {name: wireguard, mas: 1451685025}
- {name: mactap, github: jaskirat1616/mactap-app, asset: 'MacTap-.*\.zip$', app: MacTap.app, arch: arm64, macbook: true}
```

| Key | Meaning |
|---|---|
| `name` | what the log calls it (and what `apps_skip` matches) |
| `cask` | Homebrew cask (macOS). `appdir: true` installs it into `settings.macos.cask_appdir` instead of `/Applications` |
| `mas` | Mac App Store id (needs an App Store that is signed in); used when there is no cask |
| `flatpak` | Flathub id (Linux desktops) |
| `github`, `asset`, `app` | an app with no cask that ships only in GitHub releases (macOS): the latest release's zip matching `asset` is unpacked with `ditto`, its signature checked (intact, Developer ID, accepted by Gatekeeper) and `app` copied into `/Applications`. Installed again when a newer release is out; skipped with casks (`install_casks: false`) |
| `arch` | `arm64`: Apple Silicon only |
| `macbook` | `true`: MacBooks only (apps that need the laptop's hardware) |

`ansible/tests/apps_check.py` looks every id up in its store (Homebrew's API for casks and formulae, Apple's lookup
for App Store ids, Flathub's API for flatpak ids, GitHub's API for release apps, `apt-cache` for apt names) and prints the name each one resolves to;
CI runs it on every change, so a typo or a withdrawn app fails there instead of on a machine. Run it yourself after
adding an app: `python ansible/tests/apps_check.py`.

### The other keys of a bundle

| Key | What it is |
|---|---|
| `runtimes` | languages mise installs: `node`, `python`, `ruby`, `java` (a list; the first is the default), `go`, `rust`, `uv`. A version, `lts` or `latest` |
| `npm` | global npm packages (with mise's node), installed when missing |
| `gems` | Ruby gems installed into mise's Ruby on macOS (fastlane, cocoapods); they need the `runtimes` bundle too |

`taps` (top level) are the Homebrew taps (each trusted as a whole), with the formulae and casks used from them.

Windows: `windows/install.ps1` has its own winget list.
