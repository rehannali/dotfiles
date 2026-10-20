# dotfiles

My machines, set up with [Ansible](https://docs.ansible.com): packages, apps, runtimes, macOS settings and the
dotfiles themselves. It runs on macOS (Apple Silicon and Intel) and on Debian-based Linux, including WSL2.
Windows only gets a winget list (`windows/install.ps1`), and I don't test it.

You are welcome to take what is useful. Most things you'd want to change (name, email, fonts, theme, which apps
a machine gets) are variables, not code, see [docs/configuration.md](docs/configuration.md).

## Install

On the machine itself, one command:

```sh
curl -fsSL https://raw.githubusercontent.com/rehannali/dotfiles/main/bootstrap.sh | bash -s -- --host macbook
```

`--host` is the machine's name in `ansible/inventory/hosts.yml`; that decides what it gets. Leave it out and the
machine's hostname is used. A machine that is not in the inventory yet gets what a group gets:

```sh
curl -fsSL https://raw.githubusercontent.com/rehannali/dotfiles/main/bootstrap.sh | bash -s -- --host new-mac --group mac_work
```

From your laptop, to machines you reach over SSH (servers, a second Mac):

```sh
cd ansible
ansible-galaxy collection install -r requirements.yml
ansible-playbook site.yml -l homeserver -K         # -K asks for the sudo password on that machine
ansible-playbook site.yml -l servers -K            # a whole group
ansible-playbook site.yml -l macbook --check --diff   # what would change, without changing it
ansible-playbook site.yml -l macbook --tags dotfiles  # one part only
```

A machine you push to needs `ansible_host` / `ansible_user` in the inventory, your SSH key, and python3 (on a
Mac: turn on Remote Login and install the Command Line Tools first; `bootstrap.sh` does that part on the machine).

`bootstrap.sh` does what has to happen before Ansible can run, then runs it:

1. asks for your sudo password once and keeps it unlocked for the rest of the run
2. macOS: installs the Xcode Command Line Tools without the click-through dialog, then Homebrew. Homebrew's own
   installer refuses Intel Macs, although `brew` still works there (Tier 3, until September 2027), so on Intel
   it clones Homebrew/brew into `/usr/local/Homebrew` like the old installer did. Linux: makes sure `git` and
   `curl` are there
3. with `--bitwarden`: logs in to Bitwarden and unlocks the vault
4. clones this repo to `~/.dotfiles` (or updates it), installs Ansible with uv (its own Python, nothing in the
   system's), and runs `ansible/site.yml` for this machine
5. if Xcode needs your Apple ID's two-factor code, runs that last, on your terminal

Every option is in `bootstrap.sh --help`; every variable, by scenario, in [docs/environment.md](docs/environment.md).

## Machines

`ansible/inventory/hosts.yml` lists the machines by kind. Rename the example hosts to yours.

| group          | gets                                                                           |
| -------------- | ------------------------------------------------------------------------------ |
| `mac_personal` | everything                                                                     |
| `mac_work`     | the development setup, without the personal apps (`casks_skip`) and App Store  |
| `servers`      | command-line tools and the terminal setup (`gui_apps: false`)                  |
| `wsl`          | the same as servers                                                            |

What every machine gets is in `inventory/group_vars/all/` (`main.yml` has the switches, `packages.yml` the
packages); a group changes it in `group_vars/<group>.yml`, one machine in `host_vars/<host>.yml`. Adding a package
for the office Macs only, leaving one out, or uninstalling one everywhere is a line there, see
[docs/configuration.md](docs/configuration.md).

## What a run does

`ansible/site.yml`, one part after the other (`--tags` runs one):

| part       | does                                                                                                    |
| ---------- | ------------------------------------------------------------------------------------------------------- |
| `dotfiles` | links the files in `home/` into your home directory, writes the templates (`*.j2`), fetches secrets      |
| `packages` | apt on Linux; on macOS Homebrew taps (trusted item by item), formulae, casks, App Store apps; removals    |
| `shell`    | Oh My Zsh with its plugins and theme, tmux plugins, iTerm2 integration, zsh as the login shell           |
| `mise`     | the mise config from `packages.yml`, then runtimes (node, python, ruby, java, go, rust, uv) and tools     |
| `dev`      | gems into mise's Ruby (fastlane, CocoaPods), global npm packages, Flutter with fvm                        |
| `macos`    | Dock, Finder and trackpad settings, Touch ID for sudo                                                    |
| `xcode`    | the newest Xcode this Mac can run, and the iOS simulator runtime that goes with it                       |

Every install is tried 3 times (`install_retries`); what still fails is listed in a report at the end and the run
goes on. Run it again once the cause is fixed: only what is missing is installed.

## Dotfiles

`home/` is laid out exactly like your home directory. A plain file there (`home/.zshrc`, `home/.config/nvim/...`) is
**linked**, so editing `~/.zshrc` edits the checkout in `~/.dotfiles`: commit and push from there. A file ending in
`.j2` is a template (it needs your name, a setting or the OS): edit it in the repo, then
`ansible-playbook site.yml -l <host> --tags dotfiles`. A file that was in the way of a link is moved to
`~/.dotfiles-backup/<time>/` first, nothing is lost. GUI-only configs (alacritty, wezterm, karabiner, hyper) stay
off machines without `gui_apps`, and karabiner's config is copied instead of linked, because the app replaces the
file when it saves.

## Where packages come from

Homebrew stopped building bottles for Intel Macs, so on those a normal `brew install` can mean compiling (one try
pulled in LLVM and ran for hours). So the package manager depends on the machine:

| | CLI tools | System packages | Apps | Languages |
|---|---|---|---|---|
| Apple Silicon | Homebrew | Homebrew | casks | mise |
| Intel Mac | mise | Homebrew if there is a bottle, else MacPorts, else mise | casks | mise |
| Linux | mise | apt | | mise |

A tool is never installed by two managers. The rule lives in one place, `ansible/filter_plugins/tool_plan.py`,
and `packages.yml` lists every tool with the name each manager knows it by.

On Intel, a few tools have no Intel build in mise: atuin, eza and git-delta are compiled by mise with its Rust (a
few minutes), btop comes from Homebrew. Homebrew formulae with no Intel bottle (ffmpeg, nmap and others) come from
MacPorts where it has a prebuilt Intel package (installed on demand; its tools are last on PATH), then from mise
where an entry has a `mise_fallback` (ansible, ios-deploy); the rest is reported and skipped, never compiled. Ruby
has no prebuilt Intel build either and is compiled once.

## Secrets from Bitwarden

Optional. Tokens and keys stay in your vault, never in this repo. Turn it on with `bitwarden: true` in the
inventory or `bootstrap.sh --bitwarden`, list the environment variables you want in
`inventory/group_vars/all/secrets.yml`, and they are written to `~/.config/dotfiles/secrets.zsh` (mode 600).
Logging in on your own machine versus a work machine: [docs/bitwarden.md](docs/bitwarden.md).

## Xcode

By default the newest Xcode release this Mac can run is installed, plus the iOS simulator runtime that goes with
it, so an Intel Mac and an Apple Silicon Mac end up on different versions. Pin them in
`inventory/group_vars/all/toolchain.yml` or with `--xcode` / `--ios-runtime`. Ansible can't type Apple's two-factor
code for you: with a saved fastlane session (Bitwarden, see [docs/bitwarden.md](docs/bitwarden.md)) or a `.xip` you
downloaded (`DOTFILES_XCODE_XIP`) it installs Xcode itself; otherwise `bootstrap.sh` runs that one step at the end
on your terminal. `--no-xcode` leaves Xcode out.

## Checks and CI

`.github/workflows/dotfiles.yml` lints the playbook (`ansible-lint`), checks the package list (one manager per tool,
tap trust lists), renders every template for every kind of machine, then runs `bootstrap.sh` for real on an Ubuntu
runner (as a server), a macOS Intel runner and a macOS Apple Silicon runner. `scripts/check-install.py` then looks
at what ended up on the machine: every expected command is there, comes from the right package manager, starts,
and every binary is built for that OS and CPU. Manual runs can also install Xcode on a runner, using a saved Apple
session instead of the two-factor code: see [docs/ci.md](docs/ci.md).

To check a change without installing anything:

```sh
cd ansible
ansible-lint
python tests/packages_check.py                       # needs ansible-core and PyYAML
ansible-playbook -i localhost, -c local tests/render.yml
ansible-playbook site.yml -l <host> --check --diff   # on a machine: what a run would change
```

## Moving from the chezmoi version

These dotfiles used to be applied by chezmoi. Run `bootstrap.sh --host <name>` once: the files chezmoi wrote are
moved to `~/.dotfiles-backup/<time>/` and replaced by links into `~/.dotfiles`. Afterwards the old checkout
(`~/.local/share/chezmoi`) and chezmoi's config (`~/.config/chezmoi`) are no longer used and can be deleted.
