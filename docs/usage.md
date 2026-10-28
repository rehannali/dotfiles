# Using it

The short version: the repo lives in a checkout on every machine (wherever you cloned it; `~/.dotfiles` when bootstrap
cloned it, `dot cd` prints it), `dot` applies it, `dot save` sends your changes to GitHub, `dot sync` brings them to
another machine. How the setup is put together, and how to describe your machines, is in
[setup-guide.md](setup-guide.md).

## A new machine

```sh
curl -fsSL https://raw.githubusercontent.com/rehannali/dotfiles/main/bootstrap.sh | bash -s -- --home      # or --office
```

`--host` is the machine's name in `ansible/inventory/hosts.yml`. A machine that isn't there yet:
`--host new-mac --group mac_work` (or `mac_personal`, `servers`, `wsl`), and add it to `hosts.yml` afterwards so it
keeps its group. Everything `bootstrap.sh` asks and does is in the [README](../README.md#install).

From then on the machine has the checkout and the `dot` command.

## Every day: `dot`

| Command | Does |
|---|---|
| `dot` or `dot apply` | set this machine up from the checkout as it is now (no `git pull`) |
| `dot apply --tags dotfiles` | only one part: `dotfiles`, `packages`, `shell`, `mise`, `dev`, `macos`, `xcode` |
| `dot check` | show what `dot apply` would change, change nothing |
| `dot sync` | `git pull`, then apply: picks up what you changed on another machine |
| `dot save "message"` | commit everything you changed in the checkout and push it |
| `dot status` | which machine and group this is, its saved choices, what is changed or not pushed yet |
| `dot remember 'gui_apps: false'` | keep a setting for this machine on every run (see below) |
| `dot audit` | check that everything this machine should have is there, from the right manager, and starts |
| `cd "$(dot cd)"` | go to the repo |

Extra options after the command go to `ansible-playbook`, e.g. `dot apply -e install_casks=false` (that run only).

### This machine's choices

What you told `bootstrap.sh` (`--name`, `--email`, `--cli`, `--no-xcode`, `--no-casks`, `--bitwarden`, ...) is kept in
`~/.config/dotfiles/local.yml`, and every `dot apply` / `dot sync` uses it, so a later run does not install what you
left out. If no name or email for git is set anywhere, the first run asks and keeps them there too. The file is
an inventory with this machine's variables only, outside the repo (it is per machine, and has your email in it):

```yaml
all:
  hosts:
    office-mac:
      git_email: "you@company.com"
      install_xcode: false
```

`dot status` shows it. Change or delete a line to change a choice, or `dot remember 'install_xcode: true'`. A value
in `host_vars/<host>.yml` in the repo wins over it, and `-e KEY=VALUE` wins over both for one run.

With `bitwarden` on, `dot` unlocks the vault before it runs (it asks for the master password, or uses
`BW_PASSWORD`); log in once with `bw login` first. `BW_SESSION` set in your shell skips the question.

## Changing a dotfile

Plain files in `home/` are **linked**: `~/.zshrc` *is* `<checkout>/home/.zshrc`. Edit it where you like, it takes
effect in the next shell, then `dot save "zsh: new alias"`.

Templates (`home/**/*.j2`: `.gitconfig`, `.zshenv`, `.zprofile`, wezterm fonts and domains, alacritty, the secrets
file) are written, not linked, because they need your name, a setting or the OS. Edit the `.j2` in the checkout,
then `dot apply --tags dotfiles`, then `dot save`. Editing `~/.gitconfig` directly works until the next apply, which
writes the template again (the old file is kept next to it as a timestamped `~/.gitconfig.<...>~` backup).

A **new** dotfile: put it in `<checkout>/home/` at the same path it has in your home directory
(`home/.config/foo/config.toml`), `dot apply --tags dotfiles` links it (a file already in its place is moved to
`~/.dotfiles-backup/<time>/` first), `dot save`. To keep one off some machines: `dotfiles_skip_extra: [.config/foo]`
in that group's or host's vars.

Settings the templates use (git signing, fonts, theme, Dock, extra environment variables and PATH entries) are in
`ansible/inventory/group_vars/all/settings.yml`; change them for one machine with `settings_override` in
`host_vars/<host>.yml`. See [configuration.md](configuration.md#settings).

## Adding and removing packages

All in `ansible/inventory/`, then `dot apply --tags packages` (and `mise` for mise tools), then `dot save`:

| You want | Put it in |
|---|---|
| a tool for every machine that has a bundle | a line under that bundle's `tools:` in `group_vars/all/packages.yml` (`{name: jq, kind: cli, mise: jq, brew: jq, apt: jq}`; `core` is on every machine) |
| an app | a line under an `apps_*` bundle's `apps:` (`{name: slack, cask: slack, appdir: true, flatpak: com.slack.Slack}`); an app only on GitHub: `github`, `asset`, `app` (see configuration.md) |
| a whole bundle on a kind of machine | its name in `bundles:` in `group_vars/<group>.yml` |
| something on one kind of machine only | `tools_extra` / `apps_extra` in `group_vars/<group>.yml` |
| something on one machine only | the same keys (or its own `bundles:`) in `host_vars/<host>.yml` |
| leave something out on some machines | `tools_skip` / `apps_skip` there (by `name`) |
| **uninstall** something | `remove:` in `group_vars/all/main.yml` (every machine) or a group / host file |

**Commenting out or deleting a package does not uninstall it.** It only stops installing it: machines that already
have it keep it, new machines don't get it. To take it off machines, list it under `remove:`:

```yaml
remove:
  brew: [thefuck]
  cask: [kodi]
  mas: [1451685025]
  apt: [telnet]
  mise: [zig]          # also dropped from the mise config
  port: [ffmpeg]       # MacPorts, Intel Macs
```

Exactly those are uninstalled on every run, nothing else. `dot check` first shows what would go. Once it is gone
everywhere you can delete the line from `remove:` again (or leave it, it's harmless).

Which manager installs a tool on which machine (Homebrew, apt, mise, MacPorts on Intel) is decided for you from the
keys of its entry, see [configuration.md](configuration.md#packagesyml).

### mise tools are global

Runtimes (node, python, ruby, java, go, rust, uv) and the mise-installed tools go into mise's **global** config,
`~/.config/mise/config.toml` (written from `packages.yml`, don't edit it by hand). They work in every directory, in
every shell, and in IDEs and scripts that never run `mise activate`: `~/.local/share/mise/shims` is on PATH in
`.zshenv`, `.zprofile` and `.bashrc`. A run lists any tool from that config that is still not installed. A project
that needs another version puts a `mise.toml` in its own directory; that wins there only.

## Syncing machines

```
machine A:  edit ~/.zshrc, or packages.yml  ->  dot save "msg"      (commit + push)
machine B:                                     dot sync             (pull + apply)
```

`dot sync` refuses to pull over uncommitted changes on that machine that conflict with incoming ones: `dot status`
shows them; `dot save` them (or `git -C "$(dot cd)" stash`) and sync again. If two machines changed the same file,
`dot save` on the second one says the push failed: `dot sync`, resolve, `dot save` again.

From your laptop you can also update a machine you reach over SSH without logging in to it:
`cd "$(dot cd)"/ansible && ansible-playbook site.yml -l piserver -K` (on piserver the run pulls its own checkout first).

## When something did not install

Every run ends with a report of what could not be installed; the rest of the setup still ran. Fix the cause (network,
App Store not signed in, a package that was renamed) and `dot apply` again: only what's missing is installed.
`dot audit` checks the whole machine.

## Troubleshooting

**Tab prints `command not found: _autocomplete__should_insert_unambiguous`** (or `_autocomplete__unambiguous`,
`_autocomplete__should_add_space`). zsh-autocomplete keeps those helpers in its `Completions/` folder and only puts
that on zsh's function path when the plugin loads, after Oh My Zsh has already built the completion cache, so they
were never registered. `home/.zsh/omz.zsh` now adds the folder before Oh My Zsh starts and rebuilds the cache when a
plugin brings new completion files. On a machine that still has the old setup: `rm -f ~/.zcompdump* && exec zsh`
fixes it until the next plugin update; `dot sync` fixes it for good.

**`dot: <host> is not in ansible/inventory/hosts.yml`**: add the machine to `hosts.yml` under its group (and
`dot save`), or run once with `DOTFILES_GROUP=mac_work dot`.

**sudo password asked during `dot`**: macOS keeps sudo's unlock per terminal, so Ansible asks once for the steps that
need root (MacPorts, `/etc/shells`, Touch ID, Rosetta).
