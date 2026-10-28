# Setup guide

How this repo is put together, how to describe your machines, and how to set each one up: on the machine itself
or over SSH from your laptop. It also covers your name and email, Bitwarden (including a different server per
machine), and everything else you can change.

Short on time? [Set up a machine](#4-set-up-a-machine) has the commands. For daily use once a machine is set up,
see [usage.md](usage.md).

1. [How it fits together](#1-how-it-fits-together)
2. [Make it yours](#2-make-it-yours)
3. [Describe your machines](#3-describe-your-machines)
4. [Set up a machine](#4-set-up-a-machine)
5. [Name and email](#5-name-and-email)
6. [Bitwarden](#6-bitwarden)
7. [Tools and apps](#7-tools-and-apps)
8. [Dotfiles](#8-dotfiles)
9. [Everything you can configure](#9-everything-you-can-configure)
10. [Where the docs are](#10-where-the-docs-are)

## 1. How it fits together

Two separate questions decide what a machine ends up with:

- **What it gets** is decided by its **group** in `ansible/inventory/hosts.yml`: `mac_personal`, `mac_work`,
  `servers`, `wsl`, `linux_desktop`, or one you add. Each group picks **bundles** of tools and apps.
- **Where each package comes from** is decided by the **OS and CPU**, which a run detects. Your group never says
  "use brew".

| Platform | CLI tools | System packages | GUI apps |
|---|---|---|---|
| Apple Silicon Mac | Homebrew | Homebrew | casks, App Store |
| Intel Mac | MacPorts, else mise | MacPorts | casks (mycask), App Store |
| Debian, Ubuntu, Raspberry Pi OS, WSL | mise | apt | Flathub, else Snap, else vendor apt repo (desktops) |
| Other Linux (Fedora, ...) | mise | not yet: reported and skipped | |

So a personal Intel Mac and an office Intel Mac use the same managers and differ only in their bundles. An office
Apple Silicon Mac gets the office bundles from Homebrew. A Pi 4 and a Hetzner VPS in `servers` get the same tools
from apt and mise, in arm64 and x86_64 builds.

### The files

```
ansible/
├── site.yml                    the playbook: roles in order (dotfiles, packages, shell, mise, dev, macos, xcode)
├── ansible.cfg, requirements.yml
├── inventory/
│   ├── hosts.yml               your machines, each in a group
│   ├── group_vars/
│   │   ├── all/                defaults for every machine
│   │   │   ├── main.yml        switches, git name/email, bundles, *_extra / *_skip, remove
│   │   │   ├── packages.yml    every tool and app, grouped in bundles
│   │   │   ├── platforms.yml   which package manager does what, per platform
│   │   │   ├── settings.yml    taste: git, fonts, terminal theme, Dock, shell env and PATH, Flutter
│   │   │   ├── secrets.yml     environment variables to fetch from Bitwarden
│   │   │   └── toolchain.yml   Xcode / iOS simulator runtime pins
│   │   ├── mac_personal.yml    one file per group: its bundles and switches
│   │   ├── mac_work.yml
│   │   ├── servers.yml
│   │   ├── wsl.yml
│   │   └── linux_desktop.yml
│   └── host_vars/<host>.yml    exceptions for one machine (create the file when you need it)
├── roles/                      the code; you rarely need to touch it
└── tests/                      checks you can run before a change goes anywhere
home/                           your dotfiles, laid out like $HOME (*.j2 = template)
bootstrap.sh                    first-time setup on a machine
```

Two files on each machine live outside the repo:

| File | Holds |
|---|---|
| `~/.config/dotfiles/machine` | which host and group this machine is (written by every run, read by `dot`) |
| `~/.config/dotfiles/local.yml` | this machine's own choices: the `bootstrap.sh` options, the name and email you typed |

### Which value wins

The same key can be set in several places. A later layer wins:

| Order | Where | For |
|---|---|---|
| 1 | `group_vars/all/*.yml` | defaults for every machine |
| 2 | `group_vars/<group>.yml` | a kind of machine |
| 3 | `~/.config/dotfiles/local.yml` | this machine's `bootstrap.sh` options and `dot remember` settings |
| 4 | `host_vars/<host>.yml` | one machine, kept in the repo |
| 5 | `-e key=value` on the command line | one run |

A list or dict set in a later layer **replaces** the earlier one; the two are not merged. If `group_vars/mac_work.yml`
has `tools_extra: [a]` and `host_vars/office-mac.yml` has `tools_extra: [b]`, that Mac gets `b` only. The one
exception is `settings_override`, which is merged into `settings.yml` key by key (see
[section 9](#settings-git-fonts-terminal-dock-shell)).

## 2. Make it yours

If you forked the repo, point it at your fork:

- `dotfiles_repo` in `group_vars/all/main.yml`: the git URL a machine clones (used when you push to a machine over
  SSH)
- `DOTFILES_REPO=you/dotfiles` in front of `bootstrap.sh`, or change `REPO=` at its top: the repo the one-line
  installer clones
- the `curl` URL in the README

Then set your name and email ([section 5](#5-name-and-email)), and rename the example hosts in `hosts.yml` to your
machines ([section 3](#3-describe-your-machines)).

## 3. Describe your machines

Every machine has a name in `ansible/inventory/hosts.yml`, under its group. A machine you only ever set up on itself
needs nothing more. A machine you want to reach over SSH from your laptop also needs its address and user:

```yaml
all:
  children:
    macs:
      children:
        mac_personal:
          hosts:
            macbook:                     # set up on the machine itself (bootstrap.sh / dot)
        mac_work:
          hosts:
            office-intel:
            office-m3:
    servers:
      hosts:
        piserver:                        # also reachable over SSH from your laptop
          ansible_host: server.example.lan   # DNS name or IP (or "{{ private.piserver.host }}", see below)
          ansible_user: you              # the user you log in as
        hetzner:
          ansible_host: 203.0.113.10
          ansible_user: you
          ansible_port: 2222             # only when SSH is not on 22
    wsl:
      hosts:
        wsl-ubuntu:
    linux_desktop:
      hosts:
        linux-laptop:
```

The name (`macbook`, `piserver`) is what `--host` and `-l` take. It doesn't have to match the hostname, but if it does,
`bootstrap.sh` finds it without `--host`.

### The groups

| Group | Bundles | Notes |
|---|---|---|
| `mac_personal` | all 12 | everything, App Store included |
| `mac_work` | core, runtimes, dev, mac_dev, fonts, apps_dev, apps_productivity | no App Store, no personal/network apps |
| `servers` | core, runtimes, dev | `gui_apps: false` (a Pi, a VPS, a home lab box) |
| `wsl` | core, runtimes, dev | `gui_apps: false` |
| `linux_desktop` | core, runtimes, dev, media, network, apps_dev, apps_productivity, apps_personal | GUI apps from Flathub |

A machine that is not in `hosts.yml` yet can be set up anyway: `bootstrap.sh --host new-mac --group mac_work`. Without
`--group`, a Mac is set up like `mac_personal` and a Linux machine like `servers`. Add it to `hosts.yml` afterwards so
it keeps its group.

### A group of your own

1. Add it to `hosts.yml` (under `children:`, with its hosts).
2. Create `group_vars/<group>.yml` with what it gets:

   ```yaml
   ---
   bundles: [core, runtimes, dev, media]
   gui_apps: false
   ```

3. Optional: add it to `GROUP_PLATFORMS` in `ansible/tests/packages_check.py` so the checks cover it too.

### One machine that is different

Create `ansible/inventory/host_vars/<host>.yml` with only what differs:

```yaml
---
git_email: rehan@company.com      # this Mac commits with the work address
tools_skip: [docker]              # not on this one
apps_extra:
  - {name: slack, cask: slack}
install_xcode: false
```

## 4. Set up a machine

### Before the first run

`bootstrap.sh` asks the few things it must know at the start, shows what it will do, and then runs on its own:

| Asked (when nothing says it yet) | Suggested | Give it instead |
|---|---|---|
| the group of a machine that is not in `hosts.yml` | from the OS: `mac_personal` on a Mac, `wsl` in WSL, `linux_desktop` with a desktop session, else `servers` | `--group`, or add the host to `hosts.yml` |
| your name and email for git | your git config (`user.name`, `user.email`) | `--name`, `--email`, or `git_name` / `git_email` in the inventory |
| "Run the setup with these?" | Enter: yes | `--yes` |

The answers are kept for the machine in `~/.config/dotfiles/local.yml`. Everything else has a default; change it with
an option (`bootstrap.sh --help`, [environment.md](environment.md)) or in the inventory (section 9):

| Default | Change with |
|---|---|
| GUI apps on (casks and App Store on a Mac; on a Linux desktop Flathub, else Snap, else the vendor's apt repository) | `--cli`, `--no-casks`, `--no-appstore`, `--no-flatpaks`, `--no-snaps` |
| every run also upgrades (`upgrade_on_apply`) | `upgrade_on_apply: false` |
| Xcode, the newest this Mac can run; your Apple ID typed at the end | `--no-xcode`, `--xcode`, the environment or Bitwarden (Apple ID section below) |
| Bitwarden off | `--bitwarden` (section 6) |
| zsh as the login shell, the Dock / Finder / trackpad settings | `--no-chsh`, `--no-defaults` |

Fully automated (a VM, a script, CI): `--yes` with `--name` and `--email` (or with them in your git config), plus
`--no-xcode --no-appstore` or the Apple ID in the environment. Nothing is asked; a missing name or email stops only
the dotfiles part, and the report at the end says so.

There are three ways to run it. Each runs the same playbook, `ansible/site.yml`.

| Where | Command | Use it for |
|---|---|---|
| on the machine, first time | `bootstrap.sh` (the one-line installer) | a new Mac or Linux machine |
| on the machine, afterwards | `dot`, `dot sync` | daily use, picking up changes |
| from your laptop, over SSH | `ansible-playbook site.yml -l <host> -K` | servers, a second machine |

### On the machine itself (Mac, Linux, WSL)

```sh
curl -fsSL https://raw.githubusercontent.com/rehannali/dotfiles/main/bootstrap.sh | bash -s -- --host macbook \
  --name "Rehan Ali" --email rehan@example.com
```

In order, it:

1. unlocks sudo once and keeps it unlocked for the run
2. installs what Ansible can't install itself: on macOS, the Command Line Tools, and Homebrew on Apple Silicon
   (Intel Macs get none: MacPorts and mise install their tools, mycask their apps); on Linux, git and curl
3. with `--bitwarden`, logs in to Bitwarden and unlocks the vault
4. clones the repo to `~/.dotfiles`, installs Ansible with uv (its own Python), keeps your options in
   `~/.config/dotfiles/local.yml`, and runs the playbook on this machine (`-c local`, no SSH)
5. if Xcode needs your Apple ID's two-factor code, runs that last, on your terminal

Afterwards the machine has `~/.dotfiles` and the `dot` command, and `bootstrap.sh` is not needed again. Every option
is in `bootstrap.sh --help` and [environment.md](environment.md). The ones you will use most:

| Option | Does |
|---|---|
| `--host NAME` | this machine in `hosts.yml` (default: its hostname) |
| `--group GROUP` | a machine not in `hosts.yml` yet gets this group's setup |
| `--name`, `--email` | git identity ([section 5](#5-name-and-email)) |
| `--cli` | no GUI apps, only terminal tools and configs |
| `--bitwarden`, `--bw-method`, `--bw-server` | secrets from Bitwarden ([section 6](#6-bitwarden)) |
| `--no-xcode`, `--no-casks`, `--no-appstore`, `--no-macports`, `--no-flutter`, `--no-defaults`, `--no-chsh` | leave a part out |
| `--check` | show what would change, change nothing |

Options that describe the machine are kept in `local.yml`: name, email, `--cli`, `--bitwarden`, the `--no-*`
ones, `--xcode`, `--ios-runtime`, and the casks left out. `--check`, `--branch`, `--source` and
`DOTFILES_ANSIBLE_ARGS` apply to that one run only.

### From your laptop, over SSH

Good for servers: you set them up without logging in to each one. Everything runs on the server; your laptop only
drives it.

**1. Put the server in the inventory.** Over SSH there is no `--group`: the group a machine is in, in
`ansible/inventory/hosts.yml`, decides what it gets. Give it the address and the user to log in as:

```yaml
    servers:
      hosts:
        piserver:
          ansible_host: server.example.lan   # a name your DNS resolves, or an IP
          ansible_user: you
```

A name works as long as your laptop can resolve it: at home from your own DNS, away from home through the VPN's split
DNS (Tailscale, NetBird). Give the server a fixed address (a DHCP reservation) so the record never goes stale.

**2. Your git name and email in the inventory.** `bootstrap.sh` asks for them on the machine itself; over SSH nothing
is asked, and `~/.config/dotfiles/local.yml` on your laptop only applies to the laptop. Set `git_name` and
`git_email` in `group_vars/all/main.yml` (every machine) or `host_vars/piserver.yml` (that one). Without them the
dotfiles part stops and the report says so; the rest still runs.

**3. Logging in: an SSH key (best) or a password.**

- **Key:** copy it once, with the password: `ssh-copy-id you@server.example.lan`. From then on
  `ssh you@server.example.lan` asks nothing. Your `~/.ssh/config` and SSH agent are used, Bitwarden's SSH
  agent included ([bitwarden.md](bitwarden.md#ssh-agent)).
- **Password:** add `-k` (`--ask-pass`) and Ansible asks for the SSH password once. It needs `sshpass` on your laptop
  (Debian: `sudo apt install sshpass`; macOS: MacPorts `sudo port install sshpass`). Fine for the first run; then
  copy your key and drop `-k`.

What the server needs:

- python3 (Debian, Ubuntu and Raspberry Pi OS have it)
- sudo for that user: `-K` asks for its password once; with passwordless sudo, leave `-K` out

What your laptop needs: the repo, Ansible and the collections. A laptop set up with `bootstrap.sh` has all three.
Otherwise:

```sh
uv tool install --python 3.13 ansible-core
cd ~/.dotfiles/ansible && ansible-galaxy collection install -r requirements.yml
```

Then:

```sh
cd ~/.dotfiles/ansible
ansible-playbook site.yml -l piserver -K                  # one machine
ansible-playbook site.yml -l piserver -K -k               # the same, logging in with a password
ansible-playbook site.yml -l servers -K                   # a whole group
ansible-playbook site.yml -l piserver --check --diff -K   # what would change
ansible-playbook site.yml -l piserver --tags dotfiles -K  # one part only
```

The run clones the repo on the target (or updates it) and links the dotfiles there, so the machine ends up as if
`bootstrap.sh` had run, `dot` included: later you can also run `dot apply` on the server itself. Bitwarden lookups run
on your laptop, from your unlocked vault, and only their results are written on the target. `upgrade_on_apply`
works the same, so running it again from the laptop upgrades the server. Xcode on a Mac over SSH has no terminal for
a two-factor code: set `FASTLANE_SESSION` (and `XCODES_USERNAME` / `XCODES_PASSWORD`) on your laptop; they are read
there and handed to `xcodes` on the Mac.

**Macs over SSH:** run `bootstrap.sh` on the Mac once first. Over SSH the playbook does not install the Command Line
Tools or Homebrew, so a fresh Mac would report "Homebrew not installed". After that first run, turn on Remote Login
(System Settings, General, Sharing) and you can push to it like a server.

### A server with disks and Docker (piserver)

A machine with `server:` in its host_vars gets roles/server (every key in
[configuration.md](configuration.md#a-server-disks-and-docker)). `host_vars/piserver.yml` is the Raspberry Pi 4, with
the settings of its old install (taken from a backup in October 2026): the 2 TB disk, SSH on its own port, your public
keys, Docker's data and log options, NextDNS as the network's resolver, a Samba share, Glances, cloudflared, NetBird
and speedtest.

**Public template, private values.** This repo is public, so `host_vars/piserver.yml` and `hosts.yml` hold only the
layout. Its address, user, SSH port, disk UUID, LAN address, public keys, DNS forwarders and the secrets are
`{{ private.piserver.* }}`, read at run time from the item `piserver` in the Bitwarden folder `dotfiles private`
([bitwarden.md](bitwarden.md#private-values); the layout is in `ansible/private.example.yml`).

**Fresh OS or a repaired one: the same run.** It only adds what is missing and puts each config back to what host_vars
says.

1. **Flash** (if you do) with Raspberry Pi Imager: your user, hostname `piserver`, SSH with your public key. The 2 TB
   disk keeps its UUID, so it is found again without changes.
2. **DNS:** the server's name (`private.piserver.host`) points at its address (a DHCP reservation keeps it).
3. **Unlock Bitwarden** on the laptop, so the run can read the folder `dotfiles private`:
   `export BW_SESSION=$(bw unlock --raw)` (or run through `dot` with `bitwarden: true`).
4. **Run it** from the laptop. A freshly flashed OS still has SSH on port 22; the first run moves it to the private port:

   ```sh
   ansible-playbook site.yml -l piserver -K -e ansible_port=22   # first run on a fresh OS
   ansible-playbook site.yml -l piserver -K                      # every run after that
   ```

**Secrets** are keys of `private.piserver` too; for one run, an environment variable on the laptop wins. A missing one
only skips its step, and the report says what to do:

| Field of the `piserver` item | Variable | What | Without it |
|---|---|---|---|
| `cloudflared_token` | `SERVER_CLOUDFLARED_TOKEN` | the tunnel token (Cloudflare, Zero Trust, Networks, Tunnels) | `sudo cloudflared service install <token>` |
| `netbird_setup_key` | `SERVER_NETBIRD_SETUP_KEY` | a setup key (NetBird, Setup Keys) | `sudo netbird up --setup-key <key>` |
| `netbird_management_url` | | a self-hosted NetBird's management URL (`netbird_admin_url`: its dashboard, if it differs) | NetBird's cloud |
| `nextdns_profile` | `SERVER_NEXTDNS_PROFILE` | your NextDNS profile id (my.nextdns.io, the id in the URL) | NextDNS is installed, not set up |
| `samba_password` | `SERVER_SAMBA_PASSWORD` | your Samba password, set once | `sudo smbpasswd -a <you>` |

What it sets up:

| | |
|---|---|
| `/mnt/kingston2tb` | in `/etc/fstab` by UUID, with `nofail`: a missing disk never stops the boot |
| swap | a 2 GB `/swapfile` |
| SSH | the private port, your public keys; `password_authentication: true` as before (set it to false once your key works) |
| Docker data | `data-root` `/mnt/kingston2tb/docker`, and containerd's root `/mnt/kingston2tb/containerd`, where images and containers live since Docker 29 (data-root alone would leave them on the SD card) |
| Docker logs | json-file, as before: 10 files of 20 MB per container, compressed, non-blocking |
| services | `/mnt/kingston2tb/docker-services`, one folder per service, owned by you; you are in the `docker` group |
| NextDNS | listens on `localhost:53` and the server's LAN address, forwards your own zones (`nextdns_forwarders`) to your DNS servers |
| Samba | the PiNAS share (`/mnt/kingston2tb`), for you |
| Glances | the web dashboard on port 61208 |
| cloudflared, NetBird, speedtest | installed; the tunnel and the network joined when their secret is given |

If the disk is missing during a run, the Docker config is left as it is and the run says so: a server is never
switched to empty folders on the SD card. A second run changes nothing. Ookla asks once to accept its licence:
`speedtest --accept-license --accept-gdpr`.

**Not covered yet:** the old install had a `docker-update-hosts` service (it wrote the containers' names into
`/etc/hosts`, which NextDNS answers from with `use-hosts`); its script was in `/usr/local/bin`, which the backup does
not include.

### Afterwards: `dot`

| Command | Does |
|---|---|
| `dot` / `dot apply` | apply `~/.dotfiles` as it is now (no pull) |
| `dot sync` | `git pull`, then apply: picks up what another machine pushed |
| `dot check` | what apply would change (`--check --diff`) |
| `dot save "msg"` | commit and push your changes |
| `dot status` | host, group, saved choices, what is changed or unpushed |
| `dot remember 'KEY: VALUE'` | keep a setting for this machine |
| `dot audit` | check that everything this machine should have is there and starts |

Everything else about `dot` is in [usage.md](usage.md).

## 5. Name and email

Git needs both. They go into `~/.gitconfig` (`[user]`). A run that has neither writes no dotfiles and says why.

| Where | Use it when | Example |
|---|---|---|
| `group_vars/all/main.yml` | the same everywhere | `git_name: "Rehan Ali"` / `git_email: rehan@example.com` |
| `group_vars/<group>.yml` | a work address on all office Macs | `git_email: rehan@company.com` in `mac_work.yml` |
| `host_vars/<host>.yml` | one machine is different | `git_email: ...` |
| `bootstrap.sh --name ... --email ...` | you'd rather not commit them | kept in this machine's `local.yml` |
| asked on the first run | nothing above set them | the answer is kept in `local.yml` |
| `dot remember` | change it on one machine later | `dot remember 'git_email: "rehan@company.com"'` |

`dot status` shows what this machine has kept. Commit signing (GPG or SSH key) is under `git` in `settings.yml`, see
[section 9](#settings-git-fonts-terminal-dock-shell).

## 6. Bitwarden

Optional. Turn it on to keep tokens out of the repo: the run reads them from your vault and writes
`~/.config/dotfiles/secrets.zsh` (mode 600), which `.zshrc` and `.bashrc` load. It also lets Xcode installs read your
Apple ID from the vault.

### Turn it on

| For | How |
|---|---|
| every machine | `bitwarden: true` in `group_vars/all/main.yml` |
| a kind of machine | `bitwarden: true` in `group_vars/mac_personal.yml` |
| one machine | `bootstrap.sh --bitwarden` (kept in `local.yml`), `dot remember 'bitwarden: true'`, or `host_vars/<host>.yml` |
| one run | `dot apply -e bitwarden=true` |

### Say which secrets you want

In `group_vars/all/secrets.yml`, one entry per environment variable:

```yaml
secrets:
  env:
    GITHUB_TOKEN:
      item: GitHub personal access token   # the Bitwarden item's name (or id)
    NPM_TOKEN:
      item: npmjs
      field: token                         # password (default), username, notes, or a custom field's name
```

Different secrets on work machines: put a whole `secrets:` block in `group_vars/mac_work.yml`. It replaces the one
in `all/`, it isn't merged with it.

### Log in: your machine, a work machine, a different server

The first `bootstrap.sh --bitwarden` logs the `bw` CLI in. How it logs in depends on what you give it:

| Situation | Command |
|---|---|
| your own machine, API key | `BW_CLIENTID='user.xxxx' BW_CLIENTSECRET='...' bash bootstrap.sh --bitwarden` |
| email and master password | `bash bootstrap.sh --bitwarden --bw-email you@example.com` (it asks for the password and two-step code) |
| work machine with SSO | `bash bootstrap.sh --bw-method sso` |
| EU cloud | `bash bootstrap.sh --bw-server https://vault.bitwarden.eu` plus one of the logins above |
| self-hosted (Vaultwarden, company server) | `bash bootstrap.sh --bw-server https://vault.example.com` plus one of the logins above |
| work: company server and SSO | `bash bootstrap.sh --bw-server https://vault.company.com --bw-method sso` |

`--bw-server`, `--bw-method` and `--bw-email` each turn Bitwarden on. The API key and the master password
(`BW_CLIENTID`, `BW_CLIENTSECRET`, `BW_PASSWORD`) only come from the environment, never from a flag, so they stay out
of your shell history. Put them in front of the one command, not in your shell profile.

**Each machine can use a different server.** The server URL is stored by the `bw` CLI on that machine (`bw config
server` shows it), not in the repo. Your personal Mac can use `vault.bitwarden.com` while the office Mac uses
`vault.company.com` with SSO. To move a machine to another server, run `bw logout`, then `bootstrap.sh` with the new
`--bw-server` (or `bw config server <url>` and `bw login` by hand).

### Every run after that

`dot apply` and `dot sync` unlock the vault before they run. They use `BW_PASSWORD` if it is set, otherwise they ask
for the master password, and they ask nothing when `BW_SESSION` is already set in your shell. The CLI stays logged
in between runs. After a `bw logout`, run `bw login` once (or `bootstrap.sh --bitwarden` again).

Pushing to another machine over SSH uses the vault on your laptop. Unlock it there first:

```sh
export BW_SESSION=$(bw unlock --raw)
cd ~/.dotfiles/ansible && ansible-playbook site.yml -l piserver -K
```

### Apple ID: Xcode and the App Store

Decide before the first run how Xcode gets your Apple ID. `xcodes` takes the first of these that is there:

1. **Typed in.** Nothing set up: the playbook does everything else first, then runs `xcodes` on your terminal at the
   end, where you type the Apple ID, the password and the two-factor code.
2. **The environment.** `XCODES_USERNAME` and `XCODES_PASSWORD`, plus `FASTLANE_SESSION` (a saved Apple session, valid
   about a month) to skip the two-factor code; then nothing is asked ([environment.md](environment.md)).
3. **Bitwarden.** With `--bitwarden`, the item named in `settings.apple.bitwarden_item` (default `Apple ID`): its
   username and password, and optionally a custom field `FASTLANE_SESSION`
   ([bitwarden.md](bitwarden.md#apple-id-for-xcode-and-the-two-factor-code)).

CI uses the second way: a manual run with `xcode=install` reads the `FASTLANE_SESSION` secret ([ci.md](ci.md)).

The Mac App Store is different: sign in to the App Store app yourself before the run (`mas` can no longer sign in
from the command line), or leave it out with `--no-appstore`. A Mac App Store sign-in has no saved session like
`FASTLANE_SESSION`, and its two-factor code needs a person, so App Store apps are never installed in CI.

## 7. Tools and apps

Every tool and app any machine can get is in `group_vars/all/packages.yml`, in **bundles**. A machine gets an entry when
its group (or host) has that bundle. The top of the file documents every key.

### Add a command-line tool

List every manager that has it, by the name that manager uses. The run picks one per machine:

```yaml
  bundles:
    dev:
      tools:
        - {name: jq, kind: cli, mise: jq, brew: jq, apt: jq}
```

- `kind: cli`: a tool mise can install as a prebuilt binary. Apple Silicon uses `brew`; Intel Macs its `port`, else
  `mise`; Linux `mise`.
- `kind: system`: a library, daemon or big tool that needs brew or apt (`{name: ffmpeg, kind: system, brew: ffmpeg,
  apt: ffmpeg}`). For Intel Macs, add `port:` (MacPorts, where packages.macports.org has an Intel archive), else
  `mise_fallback:`.
- `kind: apple`: Apple-developer tools, macOS with GUI only.
- `bin:` is the command it provides, when that differs from `name` (the audit checks it).

### Add a GUI app

An app reaches only the platforms where it has an id:

```yaml
    apps_productivity:
      apps:
        - {name: slack, cask: slack, flatpak: com.slack.Slack}   # Mac: cask; Linux desktop: Flathub
        - {name: amphetamine, mas: 937984704}                    # Mac App Store id
```

`appdir: true` installs a cask into `settings.macos.cask_appdir` (default `~/Applications`) instead of `/Applications`.

### Choose per machine

| You want | Where |
|---|---|
| a bundle on a kind of machine | `bundles:` in `group_vars/<group>.yml` |
| one more tool or app for a group | `tools_extra:` / `apps_extra:` in `group_vars/<group>.yml`, same format as above |
| only on one machine | the same keys in `host_vars/<host>.yml` |
| leave something out | `tools_skip: [jq]` / `apps_skip: [slack]` (by `name`) |
| a new bundle | a new key under `bundles:` in `packages.yml`, then add it to the groups that should get it |

### Remove

**Commenting out or deleting an entry does not uninstall it.** It only stops installing it: machines that have it
keep it, new ones don't get it. To uninstall, list it under `remove:` (in `main.yml` for every machine, or in a group
or host file), by the name that manager uses:

```yaml
remove:
  brew: [thefuck]
  cask: [kodi]
  mas: [1451685025]
  apt: [telnet]
  mise: [zig]        # also dropped from the mise config
  port: [ffmpeg]     # MacPorts (Intel Macs)
  flatpak: [org.videolan.VLC]
```

### Check before you apply

```sh
cd ~/.dotfiles/ansible
python tests/packages_check.py   # one manager per tool; what each group gets on each platform
python tests/apps_check.py       # every cask, formula, App Store, Flathub and apt id exists
dot check                        # what this machine would change
```

Then `dot apply`, then `dot save "add jq"`, then `dot sync` on the other machines.

## 8. Dotfiles

`home/` is laid out exactly like your home directory.

- **Plain files** are **linked**: `~/.zshrc` is `~/.dotfiles/home/.zshrc`, so editing either edits the repo. Then
  `dot save`.
- **`*.j2` files** are **templates**, written from your settings: `.gitconfig`, `.zshenv`, `.zprofile`, the
  alacritty and wezterm configs, the secrets file. Edit the `.j2` in the repo, then `dot apply --tags dotfiles`.
- **A new file:** put it in `home/` at the same path it has under `~`, then `dot apply --tags dotfiles`. A file
  already in the way is moved to `~/.dotfiles-backup/<time>/` first.
- **Keep one off some machines:** `dotfiles_skip_extra: [.config/foo]` in a group or host file. GUI-only configs
  (alacritty, wezterm, karabiner, hyper) already stay off machines without `gui_apps`.

## 9. Everything you can configure

### Switches (`group_vars/all/main.yml`)

Set them in a group or host file for a kind of machine or one machine, or with `dot remember` on the machine.

| Key | Default | Does |
|---|---|---|
| `git_name`, `git_email` | `""` | git identity ([section 5](#5-name-and-email)) |
| `gui_apps` | `true` | `false`: no GUI apps or GUI configs (servers, WSL) |
| `install_casks` | `true` | macOS apps from Homebrew casks |
| `install_app_store` | `true` | Mac App Store apps (needs a signed-in App Store) |
| `install_flatpaks`, `install_snaps` | `true` | Linux desktops: apps from Flathub, and from the Snap Store for apps without a flatpak (snapd is installed if missing) |
| `install_flatpaks` | `true` | Linux desktop apps from Flathub |
| `macports_fallback` | `true` | Intel Macs: command-line tools from MacPorts |
| `upgrade_on_apply` | `true` | every run also upgrades (MacPorts, mise, Homebrew, casks); `false`: only installs, `--tags upgrade` upgrades |
| `macos_defaults` | `true` | Dock, Finder and trackpad settings |
| `touch_id_sudo` | `true` | Touch ID for sudo (Macs with a sensor, macOS 14+) |
| `install_xcode`, `install_ios_runtime` | `true` | Xcode and its iOS simulator runtime |
| `install_flutter` | `true` | Flutter with fvm |
| `login_shell_zsh` | `true` | make zsh the login shell |
| `bitwarden` | `false` | secrets from Bitwarden ([section 6](#6-bitwarden)) |
| `bundles` | `[core]` | which bundles (each group sets its own) |
| `tools_extra`, `tools_skip`, `apps_extra`, `apps_skip` | `[]` | single entries on top of the bundles, or left out |
| `remove` | empty lists | uninstalled on every run |
| `install_retries`, `install_delay` | `3`, `10` | tries per install and seconds between them |
| `dotfiles_repo`, `dotfiles_branch`, `dotfiles_dir` | this repo, `main`, `~/.dotfiles` | where the checkout comes from and lives |
| `dotfiles_skip_extra` | `[]` | dotfiles (paths under `~`) a machine does not get |

### Settings: git, fonts, terminal, Dock, shell

`group_vars/all/settings.yml` holds the defaults. To change some of them for a group or a machine, put only the keys
you change under `settings_override` in that group or host file. They are merged into the defaults:

```yaml
# host_vars/office-mac.yml
settings_override:
  git:
    sign_commits: true
    signing_format: ssh
    signing_key: ~/.ssh/id_ed25519.pub
  macos:
    dock:
      orientation: bottom
```

| Key | Default | Does |
|---|---|---|
| `git.default_branch` | `main` | `init.defaultBranch` |
| `git.sign_commits`, `git.signing_key`, `git.signing_format`, `git.gpg_program` | off, `""`, `openpgp`, `gpg` | commit signing with GPG or an SSH key |
| `git.commit_template` | `~/.stCommitMsg` | commit message template; `""` for none |
| `locale` | `en_US.UTF-8` | `LANG` in `.zshenv` |
| `terminal.font`, `terminal.font_size`, `terminal.font_size_other` | Hack Nerd Font Mono, 14, 11 | alacritty and wezterm |
| `terminal.alacritty_theme` | `blood_moon` | a theme from alacritty-theme |
| `flutter.version` | `stable` | what fvm installs |
| `macos.cask_appdir` | `~/Applications` | where `appdir: true` casks go |
| `macos.dock.*` | left, 42, autohide, no recents | Dock settings |
| `shell.env` | two Python variables | extra environment variables for every zsh |
| `shell.path` | `[]` | extra directories at the front of PATH |
| `shell.bitwarden_ssh_agent` | `auto` | `SSH_AUTH_SOCK` for Bitwarden's SSH agent: `auto`, `appstore`, `dmg`, `linux`, `snap`, `flatpak` or `off` ([bitwarden.md](bitwarden.md#ssh-agent)) |
| `apple.bitwarden_item` | `Apple ID` | the Bitwarden item with your Apple ID |
| `wsl.distribution`, `wsl.username` | `Ubuntu`, `""` | the WSL domain wezterm opens (Windows) |

### Xcode (`group_vars/all/toolchain.yml`)

Empty means the newest release this Mac can run, so an Intel Mac and an Apple Silicon Mac can end up on different
versions. To pin a version, from strongest to weakest:

1. `-e xcode_version=26.6 -e ios_runtime=26.5` for one run
2. `bootstrap.sh --xcode 26.6 --ios-runtime 26.5`, kept for this machine
3. `toolchain:` (both keys) in `host_vars/<host>.yml`
4. `toolchain.yml` for every machine

More in [configuration.md](configuration.md).

### Package managers per platform (`group_vars/all/platforms.yml`)

```yaml
platform_managers:
  macos_arm64: {cli: brew, system: brew, apps: [cask, mas]}
  macos_x86_64: {cli: port, system: port, apps: [cask, mas]}
  debian: {cli: mise, system: apt, apps: [flatpak]}
```

You change this file only when a platform changes. Intel Macs already run without Homebrew: MacPorts, else mise, for
the tools, and mycask for the casks ([tools/mycask/README.md](../tools/mycask/README.md)).

### For one run

`bootstrap.sh` options and environment variables are listed in [environment.md](environment.md). With `dot`,
anything after the command goes to `ansible-playbook`: `dot apply -e install_casks=false --tags packages`.

## 10. Where the docs are

| File | Read it for |
|---|---|
| [README.md](../README.md) | an overview: install, machines, what a run does, where packages come from |
| `docs/setup-guide.md` (this file) | how it fits together, machines and SSH, name/email, Bitwarden, everything you can change |
| [usage.md](usage.md) | daily use: `dot`, changing dotfiles, adding and removing packages, syncing, troubleshooting |
| [configuration.md](configuration.md) | reference: every key of `main.yml`, `packages.yml` entries, platforms, settings, Xcode |
| [environment.md](environment.md) | every `bootstrap.sh` option and environment variable, by scenario |
| [bitwarden.md](bitwarden.md) | secrets and logins in depth, the Apple ID and the two-factor code |
| [ci.md](ci.md) | what CI checks, and running Xcode in CI |

The inventory files explain themselves as well: the top of `packages.yml` documents every entry key, and `main.yml`
every switch.
