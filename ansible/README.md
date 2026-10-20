# Ansible

Sets up whole machines: packages, apps and services, per kind of machine. chezmoi still writes the dotfiles
(the files in your home directory); Ansible gives it its answers and decides when it runs. Both read the same
package list, `home/.chezmoidata/packages.yml`, while the setup moves over.

## Machines

`inventory/hosts.yml` lists every machine by kind. Rename the example hosts to your machines.

| group          | gets                                                                       |
| -------------- | -------------------------------------------------------------------------- |
| `mac_personal` | everything                                                                 |
| `mac_work`     | the development setup, without the personal apps (`casks_skip`) and App Store |
| `servers`      | command-line tools and the terminal setup (`gui_apps: false`)               |
| `wsl`          | the same as servers                                                        |

What a group gets is in `inventory/group_vars/<group>.yml`, one machine's exceptions in
`inventory/host_vars/<host>.yml`. Every switch, with its default, is in `inventory/group_vars/all.yml`:
`gui_apps`, `install_casks`, `install_app_store`, `macports_fallback`, `bitwarden`, `casks_skip`, `mas_skip`,
`cask_appdir`, `install_retries`, `install_delay`, and `git_name` / `git_email` (set these two).

## Running it

On the machine itself (a new Mac: this also installs the Command Line Tools, Homebrew and Ansible):

```sh
curl -fsSL https://raw.githubusercontent.com/rehannali/dotfiles/main/bootstrap.sh | bash -s -- --host macbook
# a machine that is not in the inventory yet, set up like the office Macs:
curl -fsSL https://raw.githubusercontent.com/rehannali/dotfiles/main/bootstrap.sh | bash -s -- --host new-mac --group mac_work
```

From your laptop, to machines you can reach over SSH (they need `ansible_host` / `ansible_user` in the inventory,
your SSH key, and python3; on a Mac turn on Remote Login and install the Command Line Tools first):

```sh
cd ansible
ansible-galaxy collection install -r requirements.yml
ansible-playbook site.yml -l homeserver -K        # -K asks for the sudo password on that machine
ansible-playbook site.yml -l servers -K           # a whole group
ansible-playbook site.yml -l office-mac --check   # what would change, without changing it
```

## What a run does

`site.yml`, in order:

1. **dotfiles (files)**: updates the checkout, `chezmoi init` with the inventory's answers, `chezmoi apply` without
   chezmoi's scripts (files only, including the mise config).
2. **packages**: apt on Debian-based Linux; on macOS Homebrew taps (trusted item by item), formulae, casks and App
   Store apps. On Intel Macs every formula goes down the fallbacks: Homebrew bottle, MacPorts binary (`port`), mise
   (`mise_fallback`), a source build only for `mise_intel: false` tools, else skipped. Nothing else is compiled.
3. **mise**: runtimes and command-line tools.
4. **dotfiles (scripts)**: chezmoi's remaining setup scripts (Oh My Zsh, macOS defaults, Xcode, gems, Flutter, login
   shell). Its package scripts see `DOTFILES_PACKAGES=ansible` and stand down.
5. **report**: everything that could not be installed, in one list.

Every install is tried `install_retries` times; what still fails is reported and the run goes on. Run it again
once the cause is fixed: only what is missing is installed.

## Still done by chezmoi scripts

Oh My Zsh, macOS defaults, Xcode and the simulator runtime, Touch ID for sudo, gems, npm globals, Flutter and the
login shell still run as chezmoi scripts (step 4). They move into roles next, then the server roles (hardening,
Docker services, backups) follow.
