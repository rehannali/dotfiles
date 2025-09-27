# Dotfiles

This repo contains my personal dotfiles and configuration files for various tools and applications. Feel free to explore and use them as a reference for your own setup. This uses [Chezmoi](https://chezmoi.io/) to manage the dotfiles.

## How to Use

```bash
export GITHUB_USERNAME=your_github_username
sh -c "$(curl -fsLS chezmoi.io/get)" -- init --apply $GITHUB_USERNAME
```