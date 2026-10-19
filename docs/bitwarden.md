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
| Self-hosted or EU server (any of the above) | `DOTFILES_BW_SERVER=https://vault.example.com` | `bw config server` first, then the login of your choice, see "Self-hosted or EU server" below |

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

## Apple ID for Xcode (and the two-factor code)

`xcodes` downloads Xcode with your Apple ID. It finds the credentials in this order:

1. the environment: `XCODES_USERNAME` and `XCODES_PASSWORD`
2. the Bitwarden item named in `settings.apple.bitwarden_item` (default `Apple ID`), with the Apple ID as the
   login username and password. Only if Bitwarden is on and unlocked in that run
3. otherwise `xcodes` asks

They go into the environment of the one script that installs Xcode. They are never put on a command line or
written to a file.

The two-factor code cannot be automated, `xcodes` only reads it from a prompt. What you can do:

- **Type it.** Apple sends a 6-digit code to one of your trusted devices. Once per machine.
- **Reuse a session.** Run `fastlane spaceauth -u you@example.com` once (the dotfiles install fastlane on Macs),
  enter the code there, and save the session string it prints as a custom field called `FASTLANE_SESSION` on the
  same Bitwarden item. Other machines then install Xcode with `--use-fastlane-auth` and are not asked for the code,
  until Apple expires the session (about a month, then you repeat it). Treat that string like a password: whoever
  has it is signed in as you.
- **Skip the login.** Download the `.xip` in your browser from developer.apple.com/download/all and run with
  `DOTFILES_XCODE_XIP=~/Downloads/Xcode_26.6.xip` (the version has to match `DOTFILES_XCODE_VERSION`, or what gets
  picked automatically).

The iOS runtime download has no session option, so it uses the login and may still ask for the code. It is
optional anyway, see "Xcode and the iOS runtime" in [configuration.md](configuration.md).

I tested all of this against stand-ins for `bw` and `xcodes` (the credentials arrive in the environment, the flag is
added, nothing shows up in an argument or in the output). I have not signed in to Apple with it.

## Self-hosted or EU server

The Bitwarden CLI talks to `vault.bitwarden.com` unless it is told otherwise. For your own server, or the EU cloud
(`https://vault.bitwarden.eu`), set the URL and `bootstrap.sh` tells the CLI before it logs in. It works with every
login method, so it is the same variable whether you use an API key, SSO or a password:

```sh
# API key against your own server (work machine, own machine, anything)
DOTFILES_BW_SERVER=https://vault.example.com BW_CLIENTID='user.xxxx' BW_CLIENTSECRET='...' \
  bash bootstrap.sh --bitwarden

# the same with flags for the non-secret parts; the API key still comes from the environment
BW_CLIENTID='user.xxxx' BW_CLIENTSECRET='...' bash bootstrap.sh --bw-server https://vault.example.com --bw-method apikey

# SSO against the EU cloud
bash bootstrap.sh --bw-server https://vault.bitwarden.eu --bw-method sso
```

`--bw-server`, `--bw-method` and `--bw-email` are the flags for `DOTFILES_BW_SERVER`, `DOTFILES_BW_METHOD` and
`DOTFILES_BW_EMAIL`; each of them also turns Bitwarden on. The API key and master password
(`BW_CLIENTID`, `BW_CLIENTSECRET`, `BW_PASSWORD`) have no flag on purpose: a flag would end up in your shell history
and in the process list.

The server is only set while the CLI is logged out (it refuses to change it otherwise). If this machine's `bw` is
already logged in to another server, run `bw logout` first, or log in by hand and let `bootstrap.sh` just unlock.
Doing it by hand: `bw config server <url>`; `bw config server` shows the current one.

chezmoi itself runs `bw` for every lookup, so after `bootstrap.sh` the CLI keeps pointing at that server. If you use
chezmoi without `bootstrap.sh`, set the server once with `bw config server <url>` before `bw login`.

## Not covered

Bitwarden Secrets Manager (`bws`) and `rbw` are supported by chezmoi too, but nothing here uses them. I have
only tested the login steps against a stand-in `bw`, not a real vault.
