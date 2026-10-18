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
| `DOTFILES_REPO` | | `owner/name` of the repo to apply, default `rehannali/dotfiles` |
| `DOTFILES_SOURCE` | `--source PATH` | use a local checkout instead of GitHub |
| `DOTFILES_CHEZMOI_ARGS` | | extra flags passed to `chezmoi init`, for example `--verbose` |
| | `--branch NAME` | use a branch instead of the default one |

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
| `settings.flutter.version` | `stable` | Flutter SDK that fvm installs and makes global (`stable`, `beta`, `3.35.0`...); empty to skip. Not installed in the `cli` profile |
| `settings.terminal.font` | `Hack Nerd Font Mono` | alacritty and wezterm |
| `settings.terminal.font_size` | `14` | alacritty, and wezterm on macOS |
| `settings.terminal.font_size_other` | `11` | wezterm on Linux and Windows |
| `settings.terminal.alacritty_theme` | `blood_moon` | file name from [alacritty-theme](https://github.com/alacritty/alacritty-theme) |

Flutter lands in `~/fvm/default` (a link to `~/fvm/versions/<version>`), and `~/fvm/default/bin` is on PATH, so
`flutter` and `dart` work in every shell and in IDEs. To use another version in one project: `fvm use 3.32.0`.
Android Studio and the Android SDK are not installed by the dotfiles; Flutter needs them for Android builds.

Not parameterised: the hyper config (hardly used), the Sourcetree diff/merge tool entries in the gitconfig,
tmux and neovim settings. Those are plain files you edit in `home/`.

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
