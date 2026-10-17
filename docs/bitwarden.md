# Bitwarden

Optional. If you use it, tokens and keys stay in your vault and the dotfiles only ask Bitwarden for them while
applying. It uses chezmoi's Bitwarden support, see the
[chezmoi documentation](https://www.chezmoi.io/user-guide/password-managers/bitwarden/).

## Turn it on

```sh
bootstrap.sh --bitwarden            # or DOTFILES_BITWARDEN=true
```

or answer yes to "Fetch secrets from Bitwarden" in `chezmoi init`. This sets `bitwarden = true` in
`~/.config/chezmoi/chezmoi.toml` and also `[bitwarden] unlock = "auto"`, so later `chezmoi apply` runs unlock
the vault themselves when `BW_SESSION` isn't set.

## Say which secrets you want

Edit `home/.chezmoidata/secrets.yml`:

```yaml
secrets:
  env:
    GITHUB_TOKEN:
      item: GitHub personal access token     # name or id of the Bitwarden item
    NPM_TOKEN:
      item: npmjs
      field: token                           # a custom field called "token"
```

`field` is `password` (the default), `username`, `notes`, or the name of a custom field. On the next apply
chezmoi writes `~/.config/dotfiles/secrets.zsh` with mode 600:

```sh
export GITHUB_TOKEN='...'
export NPM_TOKEN='...'
```

`.zshrc` and `.bashrc` read that file. Values with quotes or `$` in them come through unchanged. With Bitwarden
off, nothing is fetched and no file is written.

For files (an ssh key, a certificate) use an item's attachment with `bitwardenAttachmentByRef` in a template of
your own; the chezmoi page above has an example.

## Logging in

chezmoi reads secrets while it renders templates, before any of the dotfiles' scripts have run, so the vault has
to be open before `chezmoi init`. `bootstrap.sh --bitwarden` does that: it downloads the official `bw` CLI,
logs in, unlocks, and passes `BW_SESSION` on to chezmoi. How it logs in depends on what you've set:

| Situation | What you set | What happens |
|---|---|---|
| My own machine, API key | `BW_CLIENTID`, `BW_CLIENTSECRET` (from the web vault: Account settings, Security, Keys). Add `BW_PASSWORD` to avoid the last question | `bw login --apikey`, then `bw unlock` |
| Work machine, normal login | nothing, or `DOTFILES_BW_EMAIL` | asks for your email, master password and two-step code |
| SSO | `DOTFILES_BW_METHOD=sso` | `bw login --sso`, then `bw unlock` |
| Already logged in | | `bw unlock` only |

The method is picked automatically: API key if both `BW_CLIENTID` and `BW_CLIENTSECRET` are set, otherwise email and
password. Force one with `DOTFILES_BW_METHOD=apikey|sso|password`. An API key login still needs the master
password to unlock the vault: type it, or put it in `BW_PASSWORD` for the run.

Don't leave `BW_PASSWORD` or the API key in your shell profile. Export them for the one command, or read them
from somewhere safe.

## Without bootstrap.sh

Open the vault yourself, then run chezmoi:

```sh
export BW_SESSION=$(bw unlock --raw)          # or: bw login you@example.com --raw
chezmoi apply
```

## Self-hosted or EU server

Set `DOTFILES_BW_SERVER=https://vault.example.com` (for the EU cloud, `https://vault.bitwarden.eu`) and
`bootstrap.sh` tells the CLI before it logs in. Doing it by hand: `bw config server <url>`.

## Not covered

Bitwarden Secrets Manager (`bws`) and `rbw` are supported by chezmoi too, but nothing here uses them. I have
only tested the login steps against a stand-in `bw`, not a real vault.
