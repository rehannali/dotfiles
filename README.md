# Dotfiles

This repo contains my personal dotfiles and configuration files for various tools and applications. Feel free to explore and use them as a reference for your own setup. This uses [Chezmoi](https://chezmoi.io/) to manage the dotfiles.

## Prerequisites 

Although i have taken care of everything but i think `chezmoi` itself needs to install command line tools to run.

**Install Command line Tools**
```bash
sudo xcode-select --install
```

**Add Email**
`~/.config/chezmoi/chezmoi.toml`

```toml
[data]
email="your_email_address"
```


## How to Use

```bash
export GITHUB_USERNAME=your_github_username
sh -c "$(curl -fsLS chezmoi.io/get)" -- init --apply $GITHUB_USERNAME
```
