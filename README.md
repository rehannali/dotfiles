# dotfiles

My shell, terminal and tool setup, managed with [chezmoi](https://www.chezmoi.io). It runs on macOS (Apple
Silicon and Intel) and on Debian-based Linux, including WSL2. Windows only gets a winget list and the terminal
configs, and I don't test it.

You are welcome to take what is useful. Most things you'd want to change (name, email, fonts, theme, which
apps get installed) are settings, not code, see [docs/configuration.md](docs/configuration.md).

## Install

On a new machine, one command:

```sh
curl -fsSL https://raw.githubusercontent.com/rehannali/dotfiles/main/bootstrap.sh | bash
```

For a server where you only want the command-line tools and the terminal setup, no GUI apps:

```sh
curl -fsSL https://raw.githubusercontent.com/rehannali/dotfiles/main/bootstrap.sh | bash -s -- --cli
```

`bootstrap.sh` takes care of what has to happen before chezmoi can even start, then hands over to
`chezmoi init --apply`:

1. asks for your sudo password once and keeps it unlocked for the rest of the run
2. macOS: installs the Xcode Command Line Tools without the click-through dialog. (On a bare Mac the first
   `git` call, which `chezmoi init` makes, is what opens that dialog and aborts, so it can't be left to chezmoi.)
   Linux: makes sure `git` and `curl` are there
3. downloads chezmoi to a temporary folder
4. runs `chezmoi init --apply`, which installs packages, runtimes and configs

You can also skip the script and run chezmoi yourself, if you already have it and git:

```sh
chezmoi init --apply rehannali/dotfiles
```

## What it asks

Four questions, once, on the first run. The answers go to `~/.config/chezmoi/chezmoi.toml`.

| Question | Environment variable | `bootstrap.sh` flag |
|---|---|---|
| Your name (git commits) | `DOTFILES_NAME` | `--name "Ada Lovelace"` |
| Your email (git commits) | `DOTFILES_EMAIL` | `--email ada@example.com` |
| Install profile, `full` or `cli` | `DOTFILES_PROFILE` | `--full`, `--cli` |
| Fetch secrets from Bitwarden | `DOTFILES_BITWARDEN` (`true`/`false`) | `--bitwarden` |

Set them and nothing is asked. Apart from these, a run can also stop and wait for you at:

- the sudo password, once, at the start
- your Apple ID (and two-factor code) when it installs Xcode. `--no-xcode` leaves Xcode out. The run waits for
  the code on your terminal, also when you started it with `curl ... | bash`
- the Mac App Store, which has to be signed in already for the App Store apps. `--no-appstore` leaves them out
- Bitwarden, if you turned it on (see below)
- a few casks that install system extensions (macfuse, Little Snitch) want a click in System Settings

I have not run `bootstrap.sh` on a factory-fresh Mac. The Command Line Tools step uses the same
`softwareupdate` route Homebrew's own installer uses, and falls back to the normal dialog if it doesn't work.
Homebrew is installed right after it, by `bootstrap.sh` itself, and the run stops there with the installer's output
if that fails, instead of going on without `brew`. Homebrew's own installer refuses every Intel Mac ("only supported on
Apple Silicon processors"), although `brew` still works there (Tier 3, until September 2027). So on Intel
`bootstrap.sh` does what the old installer did: it clones Homebrew/brew into `/usr/local/Homebrew` and links
`/usr/local/bin/brew`.

More switches (all in `bootstrap.sh --help`): `--no-xcode`, `--no-appstore`, `--no-macports`, `--no-casks`, `--no-flutter`,
`--no-defaults` (keep your Dock and Finder settings), `--no-chsh` (keep your login shell), `--xcode VERSION`,
`--branch NAME`, and for Bitwarden `--bw-method`, `--bw-email` and `--bw-server` (a self-hosted or EU server).

Every variable, grouped by what you want to do: [docs/environment.md](docs/environment.md). Everything that is a
matter of taste (fonts, theme, git, Dock, extra variables and PATH entries) is a setting:
[docs/configuration.md](docs/configuration.md).

### Fully unattended

```sh
export DOTFILES_NAME="Ada Lovelace" DOTFILES_EMAIL=ada@example.com DOTFILES_PROFILE=full
curl -fsSL https://raw.githubusercontent.com/rehannali/dotfiles/main/bootstrap.sh | bash -s -- --no-xcode --no-appstore
```

You still type the sudo password once. If you want that gone too, make `sudo` passwordless for the run
(a `NOPASSWD` line in `/etc/sudoers.d/`, remove it afterwards). Xcode and the App Store apps need a person,
so they are the two things to leave out; install them by hand later.

## Profiles

- `full`: everything below.
- `cli`: command-line tools and the terminal setup (zsh, oh-my-zsh, tmux, neovim, git, mise runtimes). No casks,
  no App Store apps, no Xcode, no alacritty/wezterm/karabiner configs.

## Where things come from

Homebrew stopped building bottles for Intel Macs, so on those a normal `brew install` can mean compiling
(one try pulled in LLVM and ran for hours). So the package manager depends on the machine:

| | CLI tools | System packages | Apps | Languages |
|---|---|---|---|---|
| Apple Silicon | Homebrew | Homebrew | casks | mise |
| Intel Mac | mise | Homebrew if there is a bottle, else MacPorts | casks | mise |
| Linux | mise | apt | | mise |

A tool is never installed twice by two managers. The rule lives in one place,
`home/.chezmoitemplates/tool-plan`, and `home/.chezmoidata/packages.yml` lists every tool with the name each
manager knows it by. Adding a tool is one line there, see [docs/configuration.md](docs/configuration.md).

Languages (node, python, ruby, java, go, rust, uv) always come from mise. fastlane and CocoaPods are gems
installed into mise's Ruby, and the Flutter SDK is installed with fvm (`settings.flutter.version`, `stable` by default).

On Intel, a few tools have no Intel build in mise: atuin, eza and git-delta are compiled by mise with its
Rust (a few minutes), btop comes from Homebrew. Some Homebrew formulae (ffmpeg, nmap, ansible and others)
have no Intel bottle; where MacPorts has a prebuilt Intel package for them they come from there (MacPorts is
installed on demand, only when something needs it, and its tools are last on PATH so Homebrew and mise win);
if the port fails too, a tool with a `mise_fallback` (ansible, ios-deploy) comes from mise, and the rest is skipped
with a message instead of being compiled. Nothing in the package scripts stops the setup: what fails is reported
and the remaining steps still run. `--no-macports` turns the fallback off. Ruby has no prebuilt Intel
build either and is compiled once.

## Secrets from Bitwarden

Optional. Tokens and keys stay in your vault, they are never written into this repo. Turn it on with
`--bitwarden` (or `DOTFILES_BITWARDEN=true`), list which environment variables you want in
`home/.chezmoidata/secrets.yml`, and chezmoi writes them to `~/.config/dotfiles/secrets.zsh` (mode 600).
How to log in on your own machine versus a work machine is in [docs/bitwarden.md](docs/bitwarden.md).

## Xcode

By default the newest Xcode release this Mac can run is installed, plus the iOS simulator runtime that goes with it, so an
Intel Mac and an Apple Silicon Mac end up on different versions. `xcodes` does the install and asks for your Apple ID.
Pin versions with `DOTFILES_XCODE_VERSION` / `DOTFILES_IOS_RUNTIME` or in `chezmoi.toml`, see
[docs/configuration.md](docs/configuration.md). A runtime that can't be installed is skipped, you can add it from Xcode.

## Checks and CI

`.github/workflows/dotfiles.yml` runs `bootstrap.sh` for real on an Ubuntu runner (full and cli), a macOS Intel
runner and a macOS Apple Silicon runner, then `scripts/check-install.py` looks at what ended up on the
machine: every expected command is there, comes from the right package manager, starts, and every binary is
built for that OS and CPU. It runs for pull requests to `main`, pushes to `main` and when started by hand.

Manual runs can also install Xcode for real on a runner, using a saved Apple session instead of the two-factor
code: see [docs/ci.md](docs/ci.md).

To check a change without installing anything:

```sh
scripts/verify-render.sh
```

It renders every template for every OS, architecture and profile and runs `bash -n` and shellcheck on the
results. It needs chezmoi, shellcheck and python3. `VERIFY_TARGETS="linux/amd64"` limits it to some targets.
