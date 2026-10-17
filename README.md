# Dotfiles

This repo contains my personal dotfiles and configuration files for various tools and applications. Feel free to explore and use them as a reference for your own setup. This uses [Chezmoi](https://chezmoi.io/) to manage the dotfiles.

One repo, three targets: **macOS on Apple Silicon**, **macOS on Intel**, and **Linux** (Ubuntu, including WSL2). Windows (winget) is supported on a best-effort basis.

## How to Use

```bash
export GITHUB_USERNAME=your_github_username
sh -c "$(curl -fsLS chezmoi.io/get)" -- init --apply $GITHUB_USERNAME
```

### Windows

```powershell
winget install twpayne.chezmoi
chezmoi init --apply <your_github_username>
```

Run the Linux steps inside WSL2 separately (WSL is treated as Linux).

## Package policy

Homebrew moved Intel Macs to Tier 3: no new bottles, so installs and upgrades can compile from
source and stall the machine. Apple Silicon is still Tier 1. So *who* installs a tool depends on the machine:

| Target        | Single-binary CLI tools (`kind: cli`) | System packages / libs (`kind: system`) | GUI apps | Runtimes |
|---------------|---------------------------------------|-----------------------------------------|----------|----------|
| Apple Silicon | Homebrew                              | Homebrew                                | casks    | mise     |
| Intel Mac     | **mise**                              | Homebrew, only if a bottle exists       | casks    | mise     |
| Linux         | **mise**                              | apt                                     | n/a      | mise     |
| Windows       | winget                                | winget                                  | winget   | mise     |

A tool is never installed by two managers on one machine. The rule is encoded once, in
`home/.chezmoitemplates/tool-plan`, and the mise config, the Homebrew script and the apt script all read its
output, so they cannot disagree. Runtimes (node, python, ruby, java, go, rust, uv) are always mise and are
data in `packages.yml`. `kind: apple` tools (carthage, ios-deploy, swiftlint, ...) are macOS only.

Casks, Mac App Store apps and Ruby gems (fastlane, CocoaPods) are macOS only. The gems are installed
into mise's Ruby, not Homebrew's.

### Adding a tool

One entry in `home/.chezmoidata/packages.yml`, with the name each manager uses; leave a key out where
the tool is not available:

```yaml
- {name: bat, kind: cli, mise: bat, brew: bat, apt: bat}
```

For a `cli` tool, check that mise has a prebuilt release for every platform before trusting it
(run this in a scratch directory):

```bash
mise registry bat
mise lock --platform macos-x64,linux-x64 bat    # every platform must get a url
```

If macOS x86_64 is missing, set `mise_intel: false` (Intel then falls back to Homebrew). If the
tool is not a prebuilt binary at all, use `kind: system` with `brew` / `apt` names.

### Intel Macs: what to expect

Checked on 2026-10-17 against the Homebrew API and `mise lock`:

- **No Intel build in mise** (`mise_intel: false`): `atuin`, `eza`, `git-delta` (macOS releases are
  arm64-only or absent) and `btop` (no macOS release). On Intel they are installed with Homebrew, from a
  bottle if there is one and otherwise **built from source** (slow, two jobs). They are expected to be
  there, so the CI audit fails if they are not.
- **Most system formulae have no Intel bottle** at their current version, directly or through a
  dependency (`git`, `ffmpeg`, `imagemagick`, `ghostscript`, `nginx`, `nmap`, `rsync`, `php`, ...).
  `brew install --force-bottle` does not extend to dependencies, so the Homebrew script checks the formula
  *and* its not-yet-installed runtime dependencies for an Intel bottle first. If any is missing the formula
  is skipped and listed at the end; these are never compiled. macOS already ships `git`, `zsh`, `rsync` and `curl`.
  To build one on purpose: `brew install --build-from-source <formula>`.
- **Ruby compiles from source on Intel**: mise only ships a prebuilt Ruby for arm64 and Linux. The
  install script runs it with two jobs at low priority (expect several minutes once).
- `xcodes` comes from mise on Intel (Homebrew has no bottle); `aria2` is skipped there.
- `brew upgrade` is never run. Upgrade deliberately: `brew upgrade <name>`.

## Toolchain pins

Pin the Xcode and simulator versions your Mac can run in `home/.chezmoidata/toolchain.yml` before the
first `chezmoi apply`; leave them empty to skip those steps.

## CI

`.github/workflows/dotfiles.yml` runs the dotfiles for real, with chezmoi, on a **Debian-based** machine
(Ubuntu runner; same package world as WSL2), a **macOS Intel** runner and a **macOS Apple Silicon** runner.
It runs on pull requests, on pushes to `main`, and by hand (Actions → dotfiles → *Run workflow*, where you can
pick one platform and whether casks are only checked, really installed (the default for manual runs), or
skipped; pull requests and pushes only check them).

Each machine goes through the same steps:

1. `render + lint` (once, ~1 min): every template for every target, `bash -n`, shellcheck, valid mise TOML,
   one package manager per tool. See "Checking changes".
2. `chezmoi init --source <checkout> --apply`, the README flow. `DOTFILES_EMAIL` answers the one prompt;
   `DOTFILES_MAS=skip` (no App Store login on a runner); `DOTFILES_CASKS=check` verifies every cask is
   installable on that Mac without installing 80-odd GUI apps.
3. `scripts/check-install.py`, which does not trust the package lists: it asks the plan what should exist on
   *this* machine, then checks that each command resolves in a login shell, comes from the right manager
   (mise / brew / apt), starts, and that every binary and native library under mise, Homebrew, `~/.local/bin`
   and gem extensions has the right format and CPU (no Mach-O on Debian, no ELF on macOS, no x86_64 on
   Apple Silicon, no arm64 on Intel). The result is a table in the run summary; failures fail the job,
   known gaps (a formula with no Intel bottle) are warnings.

The macOS Intel label (`macos-15-intel`) is GitHub's last Intel image; change it in the workflow when it moves.

## Checking changes

```bash
scripts/verify-render.sh
```

Renders every template for darwin/arm64, darwin/amd64, linux/amd64 and windows/amd64 (os and arch are
overridden with `--override-data`, which also reaches included partials), then runs `bash -n` and
shellcheck on each rendered script, checks that scripts for another OS render empty, that the mise
config is valid TOML, and that no tool is assigned to two managers. Needs `chezmoi`, `shellcheck` and
`python3`; nothing is applied.
