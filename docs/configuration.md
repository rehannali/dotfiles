# Configuration

Everything you might want to change, and how. Nothing here needs a code change.

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

Before trusting a new `cli` tool on every platform, check what mise has:

```sh
mise registry <tool>
mise lock --platform macos-x64,macos-arm64,linux-x64 <tool>    # run in an empty folder
```

A download URL for each platform is a good sign, not proof: one tool had a URL but the program ended up
nowhere on PATH. The CI check is what actually tells.
