# Bitwarden

Optional. If you use it, tokens and keys stay in your vault and the dotfiles only ask Bitwarden for them while
applying. It uses Ansible's `community.general.bitwarden` lookup, which calls the `bw` CLI.

## Turn it on

```sh
bootstrap.sh --bitwarden            # or DOTFILES_BITWARDEN=true; kept for this machine
```

It is on by itself when `BW_CLIENTID` + `BW_CLIENTSECRET`, `BW_PASSWORD` or `BW_SESSION` is set, and whenever a run
reads the vault. Unattended, a new machine needs only these three:

```sh
export BW_CLIENTID=... BW_CLIENTSECRET=...   # web vault: Account settings, Security, Keys, View API key
export BW_PASSWORD=...                        # the master password, for this command only
export DOTFILES_BW_SERVER=https://vault.example.com   # a self-hosted server (once, before the first login)
bootstrap.sh --yes --home                     # or --office
```

Without `BW_PASSWORD`, bootstrap asks for the master password itself (hidden).

## Where each value comes from

For every value, the first place that has it:

1. **Bitwarden**: a field of `dotfiles.<host>`, else of the machine's group items (`dotfiles.mac_personal`, ...),
   else of `dotfiles.all`
2. **`~/.config/dotfiles/env`**: your own file, for a setup without Bitwarden (below)
3. **the environment of the run**: `DOTFILES_NAME` / `DOTFILES_EMAIL` (`--name` / `--email`), the tokens listed in
   `secrets.from_environment`, `SERVER_*`, `XCODES_*`. For one run only: what the setup exported itself
   (`DOTFILES_EXPORTED`) is not taken back from the shell, so a value removed from the vault or the file goes away
4. **what you typed once**: the name and email bootstrap or `dot` asked for (`git_name_asked` / `git_email_asked` in
   `~/.config/dotfiles/local.yml`)

## Environment variables: where they end up

Every name in capitals with underscores (`GH_TOKEN`, `MY_API_KEY`) from Bitwarden or `~/.config/dotfiles/env` is
exported in `~/.config/dotfiles/secrets.zsh` (mode 600), which `~/.zshenv` loads, so every zsh has it (terminals,
scripts, IDEs, cron); `~/.bashrc` loads it for bash. Each name once:

- a name one of **your own shell files** already sets (`export GH_TOKEN=...` in `~/.zlogin`, `~/.profile`,
  `~/.zshrc.local`, ...; the list is `settings.shell.own_files`) is updated there, in place, and not written again;
  that file becomes mode 600 (a backup of it is kept)
- a name also in `settings.shell.env` is exported once, with the vault's / file's value

The report at the end says where each one is: `OK: GH_TOKEN exported in ~/.zlogin (updated in place)`.

## Without Bitwarden: ~/.config/dotfiles/env

```sh
cp "$(dot cd)"/ansible/env.example ~/.config/dotfiles/env   # dot cd: where your checkout is
chmod 600 ~/.config/dotfiles/env
$EDITOR ~/.config/dotfiles/env            # NAME=value lines
dot apply                                  # or bootstrap.sh on a new machine (create the file first)
```

`ansible/env.example` shows the layout: `DOTFILES_NAME` / `DOTFILES_EMAIL` for git, your tokens (`GITHUB_TOKEN=...`),
and the setup's own variables (`XCODES_*`, `SERVER_*`), which are read but not exported. `export ` in front and quotes
around a value are fine. Change a line and run `dot apply` again; delete a line and the variable goes away. With
Bitwarden too, a field of the same name wins.

## The login, kept after the first setup

Once the vault opened, bootstrap keeps `BW_CLIENTID`, `BW_CLIENTSECRET` and `BW_PASSWORD` in the OS secret store: the
macOS Keychain, or the Secret Service on Linux (`secret-tool`, package `libsecret-tools`). Nothing goes in a file.
`DOTFILES_BW_REMEMBER=false` keeps nothing. From then on, without typing anything:

- `bw` in a terminal unlocks on its first use and keeps the session in that shell (`~/.config/shell/bitwarden.sh`);
  `bw lock` ends it
- `dot apply` / `dot sync` unlock before the run
- a plain `ansible-playbook` run unlocks too (`ansible/vars_plugins/private.py`)

All three use `dotfiles-secret` (`~/.local/bin`): `dotfiles-secret bw-session` logs in with the API key if the CLI is
logged out, then unlocks with the master password and prints the session. `dotfiles-secret delete BW_PASSWORD` (or
`BW_CLIENTID`, `BW_CLIENTSECRET`) forgets one; the Keychain app lists them under "dotfiles".

## A Mac's values, and checking they are in place

Each machine's values are the custom fields of Bitwarden items named after the inventory (more under
[Private values](#private-values)). A machine reads `dotfiles.all`, then its groups', then its own; a later one wins:

| Item | Fields |
|---|---|
| `dotfiles.all` | what every machine shares: `git_name` |
| `dotfiles.mac_personal` | every personal Mac, Intel or Apple Silicon: `git_email`, `apple_id_item`, tokens (`GITHUB_TOKEN`, ...) |
| `dotfiles.mac_work` | the office Mac: `git_email` (the work one), `apple_id_item: none` or its own, work tokens |
| `dotfiles.<host>` | only what one machine needs on its own (piserver's address, disk, secrets) |

`git_name` / `git_email` become the git identity (bootstrap stops asking for them). `apple_id_item` is the login item
xcodes signs in with, by name or id (an id when several items share a name); `none` = no Apple ID from Bitwarden.
Every field named like an environment variable (UPPER_CASE) is exported in `~/.config/dotfiles/secrets.zsh`, so
adding a token is adding a field, no repo change. `GITHUB_TOKEN` there is what `gh`, git (through gh's credential
helper) and mise's GitHub downloads use.

At the end of every run the report checks each of them and prints OK or MISSING, never a value:

- git `user.name` / `user.email` are the vault's
- `secrets.zsh` has mode 600, and each variable read back from it has the vault's value
- GitHub accepts `GITHUB_TOKEN` (`gh auth status`)
- the Bitwarden SSH agent answers and has keys
- the `Apple ID` item can be read (when Xcode is installed)

What is missing is listed with the rest of the report under "NOT done".

## Say which secrets you want

The simplest is a field on the machine's item (above). For a secret that lives in an item of its own, edit
`ansible/inventory/group_vars/all/secrets.yml`:

```yaml
secrets:
  env:
    GITHUB_TOKEN:
      item: GitHub personal access token     # name or id of the Bitwarden item
    NPM_TOKEN:
      item: npmjs
      field: token                           # a custom field called "token"
```

`field` is `password` (the default), `username`, `notes`, or the name of a custom field. On the next run the
dotfiles role writes `~/.config/dotfiles/secrets.zsh` with mode 600:

```sh
export GITHUB_TOKEN='...'
export NPM_TOKEN='...'
```

`.zshrc` and `.bashrc` read that file. Values with quotes or `$` in them come through unchanged. With Bitwarden
off, nothing is fetched and no file is written.

Files (an ssh key, a certificate) are not handled yet; `bw get attachment` in a task of your own would do it.

## Logging in

The playbook reads secrets while it runs, so the vault has to be open before it starts. `bootstrap.sh --bitwarden`
does that: it downloads the official `bw` CLI, logs in, unlocks, and passes `BW_SESSION` on to Ansible. How it logs
in depends on what you've set:

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

## Every run after that

`bootstrap.sh --bitwarden` keeps `bitwarden: true` for this machine (`~/.config/dotfiles/local.yml`), and `dot apply`
/ `dot sync` unlock the vault before they run: they ask for the master password, or use `BW_PASSWORD`, or nothing
when `BW_SESSION` is already set. The CLI stays logged in between runs; after `bw logout`, run `bw login` once.

## Without bootstrap.sh

Open the vault yourself, then run the playbook (the lookups run where `ansible-playbook` runs, so also when you
push to another machine, the vault on your laptop is used):

```sh
export BW_SESSION=$(bw unlock --raw)          # or: bw login you@example.com --raw
cd ansible && ansible-playbook site.yml -l piserver -e bitwarden=true
```

## Apple ID for Xcode (and the two-factor code)

`xcodes` downloads Xcode with your Apple ID. It finds the credentials in this order:

1. the environment: `XCODES_USERNAME` and `XCODES_PASSWORD`
2. the Bitwarden item named in `settings.apple.bitwarden_item` (default `Apple ID`), with the Apple ID as the
   login username and password. Only if Bitwarden is on and unlocked in that run
3. otherwise `xcodes` asks

They go into the environment of the one task that installs Xcode. They are never put on a command line or
written to a file.

The two-factor code cannot be automated, `xcodes` only reads it from a prompt, and Ansible gives its tasks no
terminal. What you can do:

- **Type it.** The run writes the install command to `~/.cache/dotfiles/xcode-install.sh`, and `bootstrap.sh` runs
  it at the end on your terminal. Apple sends a 6-digit code to one of your trusted devices. Once per machine.
- **Reuse a session.** Run `fastlane spaceauth -u you@example.com` once (the dotfiles install fastlane on Macs),
  enter the code there, and save the session string it prints as a custom field called `FASTLANE_SESSION` on the
  same Bitwarden item. Other machines then install Xcode with `--use-fastlane-auth` and are not asked for the code,
  until Apple expires the session (about a month, then you repeat it). Treat that string like a password: whoever
  has it is signed in as you.
- **Skip the login.** Download the `.xip` in your browser from developer.apple.com/download/all and run with
  `DOTFILES_XCODE_XIP=~/Downloads/Xcode_26.6.xip` (the version has to match `--xcode`, or what gets picked
  automatically).

With a session or a `.xip` the run installs Xcode itself, also when you push to the Mac from another machine.

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

Ansible runs `bw` for every lookup, so after `bootstrap.sh` the CLI keeps pointing at that server. Without
`bootstrap.sh`, set the server once with `bw config server <url>` before `bw login`.

## Private values

The repo is public, so personal and secret values are not in it: the files hold templates
(`{{ private.piserver.ssh_port }}`), and the values come from Bitwarden at run time. `private` is filled by
`ansible/vars_plugins/private.py` from:

1. the file `~/.config/dotfiles/private.yml` (or `DOTFILES_PRIVATE_FILE`), if it exists: outside the repo, mode 600,
   for a machine without Bitwarden; the layout, with example values, is `ansible/private.example.yml`
2. else Bitwarden, from the unlocked vault (`BW_SESSION`): items named `dotfiles.<host>` like
   `host_vars/<host>.yml`, or `dotfiles.<group>` like `group_vars/<group>.yml` (merged as above) (the prefix is `DOTFILES_PRIVATE_PREFIX`), in any folder; a `dotfiles` folder keeps them
   together

Each value is its own custom field of the item, so an edit to one cannot break another:

| Bitwarden | Ansible |
|---|---|
| item `dotfiles.piserver` (a secure note) | `private.piserver` |
| custom field `ssh_port`, value `2222` | `private.piserver.ssh_port` = `"2222"` |
| field `authorized_keys` added twice | a list of two keys |
| a boolean field | `true` / `false` |

Only fields are read; the item's notes are yours, for comments.

Secrets (`cloudflared_token`, `netbird_setup_key`, `nextdns_profile`, `samba_password`) are best hidden fields. A
missing or empty field is the same as an empty value. One run reads the items once (`bw list items --search dotfiles.`),
and only for the hosts it uses: a host whose inventory refers to `private` stops with a message saying how to unlock,
or which item to create; no other host is affected.

**Fill it from a file** (once, or again after changing the file: an existing item gets the file's fields). Write your
values in the layout of `ansible/private.example.yml`, outside the repo, then:

```sh
export BW_SESSION=$(bw unlock --raw)
uv run --no-project --with pyyaml python3 ansible/vars_plugins/private.py import ~/private.yml
shred -u ~/private.yml                    # or rm: it is in the vault now
```

It creates `dotfiles.<host>` for each host with one field per key (secrets as hidden fields, lists as repeated
fields) and prints `created dotfiles.piserver (12 fields)`. Later, change a value in the Bitwarden app: open the item,
edit the field (or add one: Custom fields, New field); then `bw sync` on the machine that runs the playbook.

**At run time** the vault has to be unlocked:

- on the machine itself: `bootstrap.sh --bitwarden` (API key: `BW_CLIENTID`, `BW_CLIENTSECRET`; master password:
  `BW_PASSWORD` or typed), or `dot` with `bitwarden: true`, which unlocks first
- from the laptop over SSH: `export BW_SESSION=$(bw unlock --raw)`, then `ansible-playbook ... -l piserver -K`
- unattended: with `BW_PASSWORD` set and no `BW_SESSION`, the run unlocks the vault itself (the CLI must be logged in
  once: `bw login --apikey` with `BW_CLIENTID` / `BW_CLIENTSECRET`), then syncs, so a value changed in the app is used

Ansible never prints the values (the secret steps use `no_log`); do not `debug: var=private`.

## SSH agent

Bitwarden can serve the SSH keys in the vault (Settings, SSH agent, in the desktop app). `~/.zshenv` points
`SSH_AUTH_SOCK` at its socket, so `ssh` and `git` use those keys in every shell. It is not set inside an SSH session,
where the forwarded agent is the right one. Setting `shell.bitwarden_ssh_agent` (`auto` by default) chooses the socket:

| Bitwarden | `shell.bitwarden_ssh_agent` | `SSH_AUTH_SOCK` |
|---|---|---|
| macOS, App Store | `appstore` | `~/Library/Containers/com.bitwarden.desktop/Data/.bitwarden-ssh-agent.sock` |
| macOS, dmg or the cask | `dmg` | `~/.bitwarden-ssh-agent.sock` |
| Linux, deb, rpm, AppImage | `linux` | `~/.bitwarden-ssh-agent.sock` |
| Linux, Snap | `snap` | `~/snap/bitwarden/current/.bitwarden-ssh-agent.sock` |
| Linux, Flatpak | `flatpak` | `~/.var/app/com.bitwarden.desktop/data/.bitwarden-ssh-agent.sock` |

With `auto` the shell looks at what is installed when it starts: on macOS an `_MASReceipt` inside Bitwarden.app means
the App Store version, otherwise the dmg or cask; on Linux the Flatpak data folder, the Snap folder, or `/opt/Bitwarden`
or an existing socket (deb, rpm, AppImage). A machine without Bitwarden gets nothing set. `off` turns it off.

On a Mac with `gui_apps` the same is also done with `launchctl setenv`, as Bitwarden's page describes, for apps that
do not start from a shell (a Git client opened from the Dock) and so never read `~/.zshenv`. A LaunchAgent,
written from `home/Library/LaunchAgents/com.dotfiles.bitwarden-ssh-agent.plist.j2`, runs it at
every login (and the playbook loads it right away), so it survives a restart. It sets `SSH_AUTH_SOCK`, which `ssh` reads,
and `SSH_AUTH_SOCKET`, the name Bitwarden's page uses in its `launchctl` line. Linux gets only the `~/.zshenv` part.
`shell.bitwarden_ssh_agent: off` removes both.

## Not covered

Bitwarden Secrets Manager (`bws`) has its own Ansible lookup (`community.general.bitwarden_secrets_manager`), but
nothing here uses it. I have
only tested the login steps against a stand-in `bw`, not a real vault.
