# Dotfiles

This repo contains my personal dotfiles and configuration files for various tools and applications. Feel free to explore and use them as a reference for your own setup. This uses [Chezmoi](https://chezmoi.io/) to manage the dotfiles.

## Platforms

| OS | Packages | Runtimes |
|---|---|---|
| macOS (Intel or Apple Silicon) | Homebrew (casks + a few CLI tools), `mas` | [mise](https://mise.jdx.dev) |
| Linux / WSL2 (Ubuntu) | `apt` | mise |
| Windows | `winget` (see `packages.yml`) | mise |

Language runtimes (node, python, ruby, java, go, rust, uv) are installed by mise from
`home/dot_config/mise/config.toml`, not by Homebrew. Homebrew moved Intel Macs to Tier 3
(no new bottles), so building runtimes through brew can compile from source on an Intel Mac.

Pin the Xcode and simulator versions your Mac can run in `home/.chezmoidata/toolchain.yml`
before the first `chezmoi apply`; leave them empty to skip those steps.

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
