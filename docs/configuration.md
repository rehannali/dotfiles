# Configuration

Everything you might want to change, and how. Nothing here needs a code change.

Looking for an environment variable? [environment.md](environment.md) lists all of them by scenario.

## Answers chezmoi asks for

Asked by `chezmoi init`, once, stored in `~/.config/chezmoi/chezmoi.toml`. Each can be given up front instead.

| Key in chezmoi.toml | Environment variable | `bootstrap.sh` | Values |
|---|---|---|---|
| `name` | `DOTFILES_NAME` | `--name` | your full name, used in `~/.gitconfig` |
| `email` | `DOTFILES_EMAIL` | `--email` | your email, used in `~/.gitconfig` |
| `profile` | `DOTFILES_PROFILE` | `--full` / `--cli` | `full` or `cli` |
| `bitwarden` | `DOTFILES_BITWARDEN` | `--bitwarden` | `true` or `false` |

To run chezmoi yourself and answer on the command line, the prompt flags match the question *text*, not the key:

```sh
chezmoi init --apply \
  --promptString "Your full name (for git commits)=Ada Lovelace" \
  --promptString "Your email address (for git commits)=ada@example.com" \
  --promptChoice "Install profile: full, or cli (command-line tools and terminal setup only, no GUI apps)=cli" \
  --promptBool "Fetch secrets from Bitwarden=false" \
  rehannali/dotfiles
```

The environment variables are shorter and I'd use those. To change an answer later, edit `chezmoi.toml` or run
`chezmoi init` again after removing the line.

## Variables for a single run

Not stored anywhere, they only affect the run they are set for.

| Variable | `bootstrap.sh` | Effect |
|---|---|---|
| `DOTFILES_XCODE=skip` | `--no-xcode` | don't install Xcode or the simulator runtime (they need your Apple ID) |
| `DOTFILES_XCODE_VERSION` | `--xcode 26.6` | install this Xcode (see "Xcode" below) |
| `DOTFILES_IOS_RUNTIME` | `--ios-runtime 26.5` | install this iOS simulator runtime |
| `DOTFILES_RUNTIME=skip` | | install Xcode but not the iOS simulator runtime |
| `DOTFILES_XCODE_XIP` | | path of an Xcode `.xip` you downloaded yourself, installed without any Apple ID login |
| `XCODES_USERNAME`, `XCODES_PASSWORD`, `FASTLANE_SESSION` | | Apple ID for `xcodes`; see [bitwarden.md](bitwarden.md) for keeping them in Bitwarden |
| `DOTFILES_FLUTTER=skip` | `--no-flutter` | don't install the Flutter SDK with fvm |
| `DOTFILES_CASKS=check` or `skip` | `--no-casks` (check) | `check`: only verify that each cask can be installed on this Mac, install none. `skip`: don't look at casks. Default is `install` |
| `DOTFILES_MAS=skip` | `--no-appstore` | no Mac App Store apps and no `mas upgrade` |
| `DOTFILES_MACPORTS=skip` | `--no-macports` | Intel Mac: a tool Homebrew has no bottle for is skipped instead of coming from MacPorts |
| `DOTFILES_DEFAULTS=skip` | `--no-defaults` | leave the Dock, Finder and trackpad preferences alone (`settings.macos.defaults = false` does it for good) |
| `DOTFILES_CHSH=skip` | `--no-chsh` | don't make zsh the login shell (that step runs `sudo chsh`) |
| `DOTFILES_CHEZMOI_VERSION` | | chezmoi release tag to download, for example `v2.73.2`; default is the latest |
| `DOTFILES_BW_METHOD`, `DOTFILES_BW_EMAIL`, `DOTFILES_BW_SERVER` | `--bw-method`, `--bw-email`, `--bw-server` | how `bootstrap.sh` logs in to Bitwarden, and a self-hosted or EU server, see [bitwarden.md](bitwarden.md) |
| `DOTFILES_REPO` | | `owner/name` of the repo to apply, default `rehannali/dotfiles` |
| `DOTFILES_SOURCE` | `--source PATH` | use a local checkout instead of GitHub |
| `DOTFILES_CHEZMOI_ARGS` | | extra flags passed to `chezmoi init`, for example `--verbose` |
| | `--branch NAME` | use a branch instead of the default one |

All of them, grouped by what you want to do: [environment.md](environment.md).

## Settings

Defaults are in `home/.chezmoidata/settings.yml`. To change one on one machine, add it to
`~/.config/chezmoi/chezmoi.toml`. Only the keys you write change.

```toml
[data.settings.git]
    default_branch = "trunk"
    sign_commits = true
    signing_key = "ABCD1234EF567890"

[data.settings.terminal]
    font = "JetBrainsMono Nerd Font"
    font_size = 13
    alacritty_theme = "dracula"
```

| Setting | Default | Used for |
|---|---|---|
| `settings.git.default_branch` | `main` | `init.defaultBranch` |
| `settings.git.sign_commits` | `false` | `commit.gpgSign` |
| `settings.git.signing_key` | empty | `user.signingKey` (GPG key id, or an SSH public key path) |
| `settings.git.signing_format` | `openpgp` | `gpg.format`, `openpgp` or `ssh` |
| `settings.git.gpg_program` | `gpg` | `gpg.program` |
| `settings.git.commit_template` | `~/.stCommitMsg` | `commit.template`, a file path; empty for none |
| `settings.apple.bitwarden_item` | `Apple ID` | Bitwarden item with your Apple ID, used by `xcodes` when Bitwarden is on |
| `settings.locale` | `en_US.UTF-8` | `LANG` |
| `settings.macos.defaults` | `true` | `false` leaves the Dock, Finder and trackpad preferences alone |
| `settings.macos.dock.orientation`, `.tile_size`, `.autohide`, `.show_recents` | `left`, `42`, `true`, `false` | the Dock preferences |
| `settings.shell.env` | the two Python variables | extra environment variables for every zsh (`~/.zshenv`), a map `NAME: value`; values may use `$HOME` |
| `settings.shell.path` | empty | extra directories in front of `PATH`, first entry wins, for example `["$HOME/go/bin"]` |
| `settings.wsl.distribution`, `.username` | `Ubuntu`, empty | the WSL domain wezterm offers on Windows; without a username wezterm uses the distribution's default user |
| `settings.flutter.version` | `stable` | Flutter SDK that fvm installs and makes global (`stable`, `beta`, `3.35.0`...); empty to skip. Not installed in the `cli` profile |
| `settings.terminal.font` | `Hack Nerd Font Mono` | alacritty and wezterm |
| `settings.terminal.font_size` | `14` | alacritty, and wezterm on macOS |
| `settings.terminal.font_size_other` | `11` | wezterm on Linux and Windows |
| `settings.terminal.alacritty_theme` | `blood_moon` | file name from [alacritty-theme](https://github.com/alacritty/alacritty-theme) |

Flutter lands in `~/fvm/default` (a link to `~/fvm/versions/<version>`), and `~/fvm/default/bin` is on PATH, so
`flutter` and `dart` work in every shell and in IDEs. To use another version in one project: `fvm use 3.32.0`.
Android Studio and the Android SDK are not installed by the dotfiles; Flutter needs them for Android builds.

Not parameterised: the hyper config (hardly used), the Sourcetree diff/merge tool entries in the gitconfig, the
tmux, neovim, atuin, btop and karabiner settings, the Spaceship prompt (`home/dot_config/spaceship`) and the trackpad
and Finder preferences in the macOS defaults script. Those are plain files you edit in `home/`. (The neovim Lua
modules are called `totu`, the author's handle; renaming the folder `lua/totu` and the five `require` / `import` lines in
`init.lua`, `lua/totu/lazy.lua` and `lua/totu/core/init.lua` is all it takes.)

Other data files you can edit: `packages.yml` (what gets installed), `toolchain.yml` (Xcode and simulator
version), `secrets.yml` (Bitwarden, see [bitwarden.md](bitwarden.md)).

## Xcode and the iOS runtime

Unless you say otherwise, the dotfiles install the newest Xcode release **that this Mac can run**, so two machines
can end up with different versions: an Intel Mac stops at an older Xcode than an Apple Silicon one, and a Mac on an
older macOS gets an older Xcode too. Betas and release candidates are never picked. It is worked out from the
[xcodereleases.com](https://xcodereleases.com) data (required macOS, supported CPUs), by `xcode-pick.py`, because
`xcodes install --latest` only warns when the newest Xcode is too new for the Mac and then installs it anyway.

`xcodes` has its own idea of what suits a Mac, and the pick follows it: `xcodes list` shows only `[Universal]` builds on
an Intel Mac and only `[Apple Silicon]` builds on an Apple Silicon one, which is why an Intel Mac stops at the last
universal Xcode. You can look at it yourself:

```sh
xcodes list                                          # what this Mac is offered
xcodes list --architecture universal                 # Intel-compatible builds
xcodes list --architecture appleSilicon              # arm64-only builds
xcodes list --architecture x86_64                    # Intel-only builds
```

The script asks `xcodes list` for the builds that fit this CPU (universal and Intel-only on Intel, Apple Silicon and
universal on Apple Silicon) and takes the newest release among them that this Mac's macOS can run, because `xcodes
list` does not look at the macOS version. If `xcodes list` fails it goes by the release data alone. When a version
exists as both an Apple Silicon and a universal build, `xcodes install` prefers the universal one.

The iOS simulator runtime defaults to the one that belongs to the Xcode that was installed.

To pin a version, in order of priority:

1. `DOTFILES_XCODE_VERSION` / `DOTFILES_IOS_RUNTIME` (or `bootstrap.sh --xcode 26.6 --ios-runtime 26.5`) for one run
2. `[data.toolchain]` in `~/.config/chezmoi/chezmoi.toml` for one machine:
   ```toml
   [data.toolchain]
       xcode_version = "26.6"
       ios_runtime = "26.5"
   ```
3. `home/.chezmoidata/toolchain.yml` for every machine (both are empty there)

The runtime is optional. If it can't be installed (no Xcode yet, Xcode's license not accepted, the download fails)
the run says so and carries on; open Xcode once and add it under Settings, Components.

## packages.yml

One entry per tool in the `tools:` list, with the name each package manager uses. Leave a key out where the tool
isn't available from that manager.

```yaml
- {name: bat, kind: cli, mise: bat, brew: bat, apt: bat}
```

| Key | Meaning |
|---|---|
| `name` | what the log calls it |
| `kind` | `cli`: a single-binary tool mise can install; `system`: libraries, daemons, big apps (Homebrew or apt); `apple`: Apple developer tools, macOS only and not in the `cli` profile |
| `mise`, `brew`, `apt` | the package name for that manager |
| `bin` | the command the tool provides, when it differs from `name` (the CI check looks for it) |
| `port` | MacPorts port, used on Intel Macs only, when Homebrew has no bottle for the tool (also instead of compiling a `mise_intel: false` tool). Set it only if `packages.macports.org/<port>/` has a `darwin_25.x86_64` archive |
| `brew_args` | options for the Brewfile line, for example `restart_service: :changed` |
| `mise_intel` | tool has no Intel Mac build in mise. A mise id (`"cargo:atuin"`) means Intel installs that instead, `false` means Intel uses Homebrew |
| `prebuilt` | a tap formula that downloads a ready-made binary (so there is no bottle to look for) |

Casks, App Store apps and gems are under `darwin:`. To stop installing something, comment it out rather than
delete it, that way it's easy to bring back.

List what you want, not what it needs. When another listed package already installs a package as a runtime
dependency with the same manager on the same machine (Homebrew installs `libyaml` with `ansible`, apt installs
`git` with `git-flow`), the entry is left out or loses that manager's key, with a comment saying where it comes
from. Only runtime dependencies count: a bottle or a prebuilt binary never installs build-only ones, so a tool
that merely needs `go` or `cmake` to be compiled does not bring them. Check a formula with
`brew deps --formula <name>` (runtime) and `brew deps --formula --include-build <name>`, and an apt package with
`apt-cache depends <name>`. Keep an entry when the dependent is not installed on some machine: Intel Macs
have no Homebrew bottle for most formulae, so something that comes with another package on Apple Silicon may be
the only copy there.

### Taps and trust

Homebrew 6 and newer load nothing from a tap you have not trusted ([Tap Trust](https://docs.brew.sh/Tap-Trust)),
because a tap's formulae and casks are Ruby code that runs as you. Each tap under `taps:` therefore lists what is
used from it:

```yaml
taps:
  - {name: xcodesorg/made, formulae: [xcodes]}
  - {name: netbirdio/tap, casks: [netbird-ui]}
```

The install script clones the tap, runs `brew trust --formula xcodesorg/made/xcodes` (or `--cask`) for exactly
those items, and writes the same list into the Brewfile as `tap "xcodesorg/made", trusted: { formulae: ["xcodes"] }`.
The whole tap is never trusted. If trusting an item fails, the tap and its items are left out and reported instead
of failing the whole run; on a Homebrew without `brew trust` nothing is done. A formula or cask from a tap that is
missing here makes `scripts/verify-render.sh` fail. `brew trust` lists what is trusted on a machine.

Before trusting a new `cli` tool on every platform, check what mise has:

```sh
mise registry <tool>
mise lock --platform macos-x64,macos-arm64,linux-x64 <tool>    # run in an empty folder
```

A download URL for each platform is a good sign, not proof: one tool had a URL but the program ended up
nowhere on PATH. The CI check is what actually tells.

### The other lists in packages.yml

| Key | What it is |
|---|---|
| `taps` | Homebrew taps, each with the exact formulae and casks that are trusted, see "Taps and trust" above |
| `runtimes` | languages mise installs on every machine: `node`, `python`, `ruby`, `java` (a list; the first is the default), `go`, `rust`, `uv`. A version, `lts` or `latest` |
| `npm` | global npm packages (with mise's node), installed once on a machine's first run |
| `darwin.gems` | Ruby gems installed into mise's Ruby on macOS (fastlane, cocoapods) |
| `darwin.casks` | Homebrew casks. `args_str` is pasted into the Brewfile line, for example `args: { appdir: "~/Applications" }` to install the app in your home folder instead of `/Applications` |
| `darwin.mas` | Mac App Store apps, `id` and `name` (needs an App Store that is signed in) |
| `darwin_arm.casks` | casks only for Apple Silicon (empty at the moment) |
| `windows.winget` | winget package ids for Windows; nothing else is done for Windows |

Comment an entry out instead of deleting it, the casks and App Store apps in the file are kept that way.

### Zsh plugins, the prompt and the alacritty themes

These are not in `packages.yml`:

- oh-my-zsh and its extra plugins (`zsh-autosuggestions`, `fast-syntax-highlighting`, `zsh-autocomplete`,
  `zsh-lsd`, `zsh-bat`, `you-should-use`, the Spaceship prompt, tmux's `tpm`, ...) are git clones listed in
  `home/.chezmoiexternals/omz.toml`. The plugin names that zsh loads are in `home/dot_zsh/omz.zsh`; plugins that wrap
  a command (`poetry`, `lsd`, `bat`, `thefuck`) are only loaded when that command exists. To add a plugin, add the
  clone to `omz.toml` and its name to `omz.zsh`.
- The Spaceship prompt is configured in `home/dot_config/spaceship/spaceship.zsh`.
- The alacritty themes are one archive pinned to a commit in `home/.chezmoiexternals/alacritty-themes.toml.tmpl`;
  change the SHA to update. They are not extracted on the `cli` profile.

### What runs, and when

`chezmoi apply` runs these scripts from `home/.chezmoiscripts` in this order. "Once" means chezmoi remembers it ran on
this machine and skips it next time; "on change" means it runs again when the script's rendered text changes (for
example because `packages.yml` changed).

| Script | When | What it does |
|---|---|---|
| `run_once_before_00-utils` | once | writes `~/.local/lib/chezmoi-utils.sh`, the helper functions the other scripts share |
| `run_once_before_01-pre-setup` | once | macOS: Rosetta (Apple Silicon), Homebrew, `mas`, `aria2` and `xcodes` (from Homebrew on Apple Silicon, from mise on Intel), then Xcode; not in the `cli` profile for the GUI parts |
| `run_onchange_before_05-install-apt-packages` | on change | Linux: `apt-get install` of the `apt` list |
| `run_once_before_10-install-omz` | once | oh-my-zsh |
| `run_onchange_11-install-packages` | on change | macOS: taps and trust, then the Brewfile (formulae on Apple Silicon, casks, App Store apps); on Intel formulae one by one, bottle only, and MacPorts binaries (`port install -b`, installed on demand) for those without a bottle |
| `run_onchange_after_10-configure-defaults` | on change | macOS: Dock, Finder, trackpad preferences |
| `run_onchange_after_12-install-mise-tools` | on change | installs mise if needed, then the runtimes and CLI tools |
| `run_onchange_after_13-install-ruby-gems` | on change | macOS, `full` profile: fastlane and cocoapods into mise's Ruby |
| `run_onchange_after_14-install-flutter` | on change | macOS and Linux, `full` profile: Flutter with fvm (skipped when `settings.flutter.version` is empty) |
| `run_once_after_00-setup-zsh-theme` | once | links the Spaceship theme into oh-my-zsh |
| `run_once_after_30-setup-additional` | once | global npm packages, iTerm2 shell integration (only if iTerm2 is installed), `mas upgrade` |
| `run_once_after_31-install-xcode-runtime` | once | macOS, `full` profile: the iOS simulator runtime |
| `run_once_after_90-change-shell` | once | makes zsh the login shell (`sudo chsh`) |
| `run_onchange_install-winget` | on change | Windows: `winget install` of the list |

To run the once-only ones again: `chezmoi state delete-bucket --bucket=scriptState`, then `chezmoi apply`.
