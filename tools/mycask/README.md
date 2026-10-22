# mycask

Installs Mac apps (casks) from Homebrew's cask definitions, without Homebrew. The Intel Mac uses it in place of
`brew install --cask`: Homebrew made Intel Tier 3 in September 2026 and drops it on 1 September 2027. Command-line
tools on that Mac come from MacPorts and mise instead (`ansible/inventory/group_vars/all/packages.yml`); a tool that
ships as a cask (claude-code, codex) is a cask here too. Apple Silicon and Linux don't use mycask.

It is one file, `mycask.py`, standard library only (it runs on the macOS system Python 3.9 too). Ansible links it to
`~/.local/bin/mycask` on Intel Macs.

## Commands

Definitions come from Homebrew's `cask.json` (formulae.brew.sh), downloaded at most once a day and reused in between.
mycask follows Homebrew's cask rules for artifacts, uninstall and zap. Before it replaces an app, it reads the new
app's own `Info.plist` and `lipo -archs`, so it never installs an update that dropped Intel or needs a newer macOS. It
keeps the installed version and skips that update from then on.

```sh
mycask install firefox                  # --adopt takes over an app already in place, --force replaces it
mycask install --appdir ~/Applications alfred   # into another folder; upgrades and uninstalls remember it
mycask bundle casks.txt                 # every token in a file (see the format below)
mycask upgrade                          # outdated casks; --greedy includes auto-updating and "latest" ones
mycask reinstall <token>                # download and install again
mycask outdated | list | info <token> | search <text>
mycask pin <token> / unpin <token>      # hold a cask at its installed version
mycask uninstall <token>                # --zap also removes settings and caches
mycask zap <token>                      # leftovers of an app, even one mycask didn't install (--appdir DIR)
mycask update                           # refresh the index now (otherwise at most once a day)
```

`casks.txt` has one token per line, `#` starts a comment. A line can name the folder its app goes to:

```
firefox
alfred --appdir=~/Applications
```

`--help` after any command lists all its options.

## Checking an install

`verify.py` reads mycask's receipts and reports anything missing or broken, with exit status 1: a cask needs its apps
and binaries in place, and every command it linked must start (no `dyld` / `Library not loaded` / wrong CPU).
`verify-casks.sh` installs, checks and uninstalls each cask of a list. `.github/workflows/mycask-verify.yml` runs it
for every cask the Intel Macs get, on a clean Intel runner (docs/ci.md).

```sh
python3 -I tools/mycask/verify.py --casks ~/.config/mycask/casks.txt
```

## Environment

| Variable | Default | |
|---|---|---|
| `MYCASK_TTL` | `86400` | seconds between automatic index refreshes |
| `MYCASK_API` | formulae.brew.sh | the cask index URL, for a mirror if formulae.brew.sh goes away |
| `MYCASK_PREFIX` | `~/.local` | where cask binaries, man pages and completions are linked |
| `MYCASK_ROOT` | `~/.local/share/mycask` | receipts and staged files |
| `MYCASK_CACHE` | `~/Library/Caches/mycask` | downloads and the cached index |
| `MYCASK_OVERRIDES` | `~/.config/mycask/casks` | `<token>.json` files used instead of the index, to pin or patch a cask |
| `MYCASK_DEBUG=1` | | full Python tracebacks |

## How the dotfiles use it

`packages.yml` stays the one place apps are listed. On an Intel Mac Ansible writes `~/.config/mycask/casks.txt` from
the machine's bundles (with `--appdir` for the apps marked `appdir: true`), runs `mycask bundle` on it, and, with
`upgrade_on_apply` (the default) or `--tags upgrade`, `mycask upgrade`. `remove.cask` in `main.yml` runs
`mycask uninstall`. The same list for every Intel Mac in the inventory is committed as `intel/casks.txt` for CI;
`tests/packages_check.py` fails when it no longer matches `packages.yml`, and `python3 tools/mycask/manifests.py`
writes it again.

## Moving an Intel Mac off Homebrew

1. `dot check` (or `ansible-playbook site.yml -l <mac> --check --diff`): the ports, mise tools and casks it would
   install. Nothing changes.
2. Back up what Homebrew had (`brew list --formula > ~/brew-formulae.txt; brew list --cask > ~/brew-casks.txt`), then
   remove it: `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/uninstall.sh)"`,
   and `sudo rm -rf /usr/local/Homebrew /usr/local/Caskroom /usr/local/Cellar` if it left them. The apps stay where
   they are. (Not required: the playbook works with Homebrew still there, and reports it.)
3. `dot apply -e mycask_adopt=true`: MacPorts and mise install the tools, mycask takes over the apps already in place
   (in `/Applications` or, for `appdir: true`, `~/Applications`) and installs the rest. Casks whose installer is a
   `.pkg` run that installer again, which needs sudo: if one fails with "a terminal is required", run
   `mycask bundle --adopt ~/.config/mycask/casks.txt` in a terminal.
4. Later runs: `dot apply` installs what is missing and upgrades the rest (`upgrade_on_apply: false` in `main.yml`
   to only install; `--tags upgrade` then upgrades on demand).

## After Homebrew drops Intel (September 2027)

Casks keep working through mycask and `cask.json` as long as formulae.brew.sh serves it (`MYCASK_API` for a mirror).
When a cask's newest version drops Intel, mycask sees it in the app's own `Info.plist` / `lipo` output, refuses the
update and keeps the installed version. For an app that matters, `mycask pin <token>`, or put a definition that still
points at an Intel download in `~/.config/mycask/casks/<token>.json`. The GitHub Intel runner is gone after August
2027: `mycask-verify.yml` stops itself from 2027-08-01.
