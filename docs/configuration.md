# Configuration

Everything you might want to change, and where. Nothing here needs a code change: it is all variables in
`ansible/inventory/`.

Looking for a `bootstrap.sh` option or an environment variable? [environment.md](environment.md) lists them all.

## Where a variable goes

| File | For |
|---|---|
| `inventory/hosts.yml` | which machines there are, and which group each is in |
| `inventory/group_vars/all/main.yml` | what every machine gets: name and email, the switches below, extra / skipped / removed packages |
| `inventory/group_vars/all/packages.yml` | the package list for every machine |
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
into `~/.gitconfig`. `bootstrap.sh --name/--email` sets them for one run. A run without them writes no dotfiles
and says so.

## Switches

All in `main.yml`, `true` unless noted:

| Switch | Effect |
|---|---|
| `gui_apps` | `false`: command-line tools and the terminal setup only. No casks, no App Store apps, no Xcode, no Flutter, no macOS defaults, no alacritty / wezterm / karabiner / hyper configs, no `apple` tools. The `servers` and `wsl` groups set it |
| `install_casks` | macOS GUI apps (Homebrew casks) |
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

## Packages per kind of machine

`packages.yml` is the list for every machine. A group or host changes it with these (in `main.yml` they are empty):

```yaml
# group_vars/mac_work.yml
tools_extra:
  - {name: awscli, kind: cli, mise: aws-cli, brew: awscli}
tools_skip: [ffmpeg, php]          # by `name`
casks_extra:
  - {name: slack, appdir: true}
  - {name: zoom}
casks_skip: [spotify, discord]     # short names work for tap casks too
mas_extra:
  - {id: 803453959, name: Slack}
mas_skip: [430255202]              # App Store ids
```

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
| `git.commit_template` | `~/.stCommitMsg` | `commit.template`, a file path; empty for none |
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

1. `bootstrap.sh --xcode 26.6 --ios-runtime 26.5` (or `-e xcode_version=26.6 -e ios_runtime=26.5`) for one run
2. `toolchain:` in `host_vars/<host>.yml` for one machine (both keys)
3. `group_vars/all/toolchain.yml` for every machine (both are empty there)

Signing in: Ansible can't type Apple's two-factor code. With a saved fastlane session (`FASTLANE_SESSION`, or the
custom field of that name on the Bitwarden item) or a `.xip` you downloaded (`DOTFILES_XCODE_XIP`) the run installs
Xcode itself. Otherwise it writes the command to `~/.cache/dotfiles/xcode-install.sh`, and `bootstrap.sh` runs that at
the end on your terminal (or run it yourself). The runtime is optional: if it can't be installed the run says so and
carries on; open Xcode once and add it under Settings, Components.

## packages.yml

One entry per tool in the `tools:` list, with the name each package manager uses. Leave a key out where the tool
isn't available from that manager.

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
| `mise_fallback` | mise tool id, used on Intel Macs only, when Homebrew has no bottle and MacPorts (no `port`, or its install failed) cannot install the tool either. It goes into the mise config |
| `mise_intel` | tool has no Intel Mac build in mise. A mise id (`"cargo:atuin"`) means Intel installs that instead, `false` means Intel uses Homebrew |
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
because a tap's formulae and casks are Ruby code that runs as you. Each tap under `taps:` therefore lists what is
used from it:

```yaml
taps:
  - {name: xcodesorg/made, formulae: [xcodes]}
  - {name: netbirdio/tap, casks: [netbird-ui], needs: [netbird]}   # the cask is listed as netbirdio/tap/netbird-ui under darwin.casks
```

The packages role taps it and runs `brew trust --formula xcodesorg/made/xcodes` (or `--cask`) for exactly those
items. `needs` lists formulae of the same tap that a cask depends on. The whole tap is never trusted. A tap that
can't be cloned or trusted is reported and the run goes on; on a Homebrew without `brew trust` nothing is done. A
formula or cask from a tap that is missing here makes `ansible/tests/packages_check.py` fail.

Before adding a new `cli` tool on every platform, check what mise has:

```sh
mise registry <tool>
mise lock --platform macos-x64,macos-arm64,linux-x64 <tool>    # run in an empty folder
```

A download URL for each platform is a good sign, not proof: one tool had a URL but the program ended up nowhere on
PATH. The CI check is what actually tells.

### The other lists in packages.yml

| Key | What it is |
|---|---|
| `taps` | Homebrew taps, each with the exact formulae and casks that are trusted |
| `runtimes` | languages mise installs on every machine: `node`, `python`, `ruby`, `java` (a list; the first is the default), `go`, `rust`, `uv`. A version, `lts` or `latest` |
| `npm` | global npm packages (with mise's node), installed when missing |
| `darwin.gems` | Ruby gems installed into mise's Ruby on macOS (fastlane, cocoapods) |
| `darwin.casks` | Homebrew casks. `appdir: true` installs the app into `settings.macos.cask_appdir` instead of `/Applications` |
| `darwin.mas` | Mac App Store apps, `id` and `name` (needs an App Store that is signed in) |
| `darwin_arm.casks` | casks only for Apple Silicon (empty at the moment) |

Windows: `windows/install.ps1` has its own winget list.
