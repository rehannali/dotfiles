# mycask

Installs Mac apps (casks) and command-line tools (formulae) from Homebrew's definitions, without Homebrew. The Intel
Mac uses it in place of `brew`. Homebrew made Intel Tier 3 in September 2026 (no new Intel bottles) and drops Intel
on 1 September 2027. Apple Silicon and Linux don't use it.

It is one file, `mycask.py`, standard library only (it runs on the macOS system Python 3.9 too). It is vendored here:
fix bugs as small patches, don't rewrite it. Ansible links it to `~/.local/bin/mycask` on Intel Macs.

## Apps (casks)

Definitions come from Homebrew's `cask.json`. mycask follows Homebrew's cask rules for artifacts, uninstall and zap.
Before it replaces an app, it reads the new app's own `Info.plist` and `lipo -archs`, so it never installs an update
that dropped Intel or needs a newer macOS. It keeps the installed version and skips that update from then on.

```sh
mycask install firefox                  # --adopt takes over an app already in place, --force replaces it
mycask install --appdir ~/Applications alfred   # into another folder; upgrades and uninstalls remember it
mycask bundle casks.txt                 # every token in a file (see the format below)
mycask upgrade                          # outdated casks; --greedy includes auto-updating and "latest" ones
mycask outdated | list | info <token> | search <text>
mycask pin <token> / unpin <token>      # hold a cask at its installed version
mycask uninstall <token>                # --zap also removes settings and caches
mycask zap <token>                      # leftovers of an app, even one mycask didn't install
mycask update                           # refresh the indexes now (otherwise at most once a day)
```

`casks.txt` has one token per line, `#` starts a comment. A line can name the folder its app goes to:

```
firefox
alfred --appdir=~/Applications
```

## Command-line tools (formulae)

Definitions come from Homebrew's `formula.json`. For each formula mycask picks the first of:

1. a Homebrew bottle for the current version that fits this Mac (Intel bottles stop at `sonoma`, which also runs on
   Sequoia and Tahoe), where every runtime dependency is also available as a bottle. Bottles go into
   `/usr/local/Cellar` with Homebrew's layout; placeholders and Mach-O load paths are relocated
2. a bottle built by this repo's CI (`.github/workflows/intel-bottles.yml`) and published in the `intel-bottles`
   release, for the current version
3. the formula's entry in the CLI map: mise or MacPorts, prebuilt binaries only (`port -b`)
4. otherwise it reports `needs-build`. It never compiles anything on the Mac.

A map entry with `"prefer": true` is used even when a bottle exists.

```sh
mycask formula setup                    # once: prepare /usr/local (sudo; refuses while Homebrew is there)
mycask formula bundle formulae.txt      # or: mycask formula install <names>
mycask formula upgrade | outdated | list | info <name>
mycask formula uninstall <name> | autoremove | pin <name> | unpin <name>
mycask formula plan --tag sequoia --file formulae.txt --json   # read-only; runs on Linux too (CI uses it)
mycask formula ci-index --bottle-dir DIR --base-url URL --existing index.json --out index.json
```

`--help` after any command lists all its options.

## Environment

| Variable | Default | |
|---|---|---|
| `MYCASK_CLI_MAP` | `~/.config/mycask/cli-map.json` | formula -> `{"mise": spec}` or `{"port": name}`, optional `"prefer": true` |
| `MYCASK_BOTTLES_URL` | empty | the CI bottle index; the dotfiles set it to this repo's `intel-bottles/index.json` |
| `MYCASK_TTL` | `86400` | seconds between automatic index refreshes |
| `MYCASK_FORMULA_PREFIX` | `/usr/local` | where bottles go (Homebrew's Intel prefix, so non-relocatable bottles work) |
| `MYCASK_PREFIX` | `~/.local` | where cask binaries, man pages and completions are linked |
| `MYCASK_ROOT` | `~/.local/share/mycask` | receipts and staged files |
| `MYCASK_CACHE` | `~/Library/Caches/mycask` | downloads and the cached indexes |
| `MYCASK_OVERRIDES` | `~/.config/mycask/casks` | `<token>.json` files used instead of the index, to pin or patch a cask |
| `MYCASK_API`, `MYCASK_FORMULA_API` | formulae.brew.sh | index URLs, for a mirror if formulae.brew.sh goes away |
| `MYCASK_DEBUG=1` | | full Python tracebacks |

## How the dotfiles use it

The lists are not edited by hand: `packages.yml` stays the one place packages are listed. On an Intel Mac Ansible
writes, from the machine's bundles:

- `~/.config/mycask/casks.txt`: its casks, with `--appdir` for the ones marked `appdir: true`
- `~/.config/mycask/formulae.txt`: its `brew` formulae
- `~/.config/mycask/cli-map.json`: each formula's `port` (unless MacPorts would have to compile it, `port_build`) or
  else its `mise_fallback`; `intel_prefer: true` in `packages.yml` becomes `"prefer": true`

The same lists for every Intel Mac in the inventory are committed in `intel/` for CI. `tests/packages_check.py` fails
when they no longer match `packages.yml`; `python3 tools/mycask/manifests.py` writes them again.

Ansible runs `mycask formula plan` first and acts on each answer: bottles through mycask, MacPorts ports with the
role's own `port-install.sh` (Ansible's sudo), and mise tools into `~/.config/mise/config.toml` (the mise role
installs them). So mycask never runs `mise use -g`, which would edit a file Ansible rewrites on every run.

## Moving an Intel Mac off Homebrew

1. `dot check` (or `ansible-playbook site.yml -l <mac> --check --diff`): the plan for every formula, the casks
   mycask would install, and a note that Homebrew is still in the way. Nothing changes.
2. Remove Homebrew: `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/uninstall.sh)"`,
   then `sudo rm -rf /usr/local/Homebrew /usr/local/Caskroom` if it left them. The apps stay where they are; the
   command-line tools Homebrew installed go away until the next step.
3. `dot apply -e mycask_adopt=true`: mycask takes over the apps already in place (in `/Applications` or, for
   `appdir: true`, `~/Applications`) and installs the rest. Casks whose installer is a `.pkg` run that installer
   again, which needs sudo: if one fails with "a terminal is required", run
   `mycask bundle --adopt ~/.config/mycask/casks.txt` in a terminal.
4. Later runs: `dot apply` installs what is missing; `dot apply --tags upgrade` also upgrades.

## Timeline

**Phase 1, now to July 2027.** Formulae come from Homebrew's Intel bottles where they still exist, from the bottles
this repo's CI builds (`intel-bottles` release) and from MacPorts or mise. When Homebrew updates a formula that CI
builds, the next daily run rebuilds it, and `mycask formula upgrade` (`dot apply --tags upgrade`) picks the new
bottle up.

**Phase 2, by July 2027.** Move every formula to MacPorts or mise while the Intel runner can still build what is
missing:

1. `mycask formula plan --no-map --file ~/.config/mycask/formulae.txt` lists what still depends on bottles (the
   `bottle` and `needs-build` lines).
2. For each one, make sure its `packages.yml` entry has a prebuilt `port` or a `mise_fallback`, add
   `intel_prefer: true`, run `python3 tools/mycask/manifests.py` and commit.
3. Uninstall the bottle first, `mycask formula uninstall <name>` (then `mycask formula autoremove` for dependencies
   nothing needs), and only then `dot apply --tags packages,mise`, which installs it from MacPorts or mise.

**Phase 3, from August 2027.** `macos-15-intel` is retired after August 2027, and Homebrew drops Intel on
1 September 2027. The workflow stops itself (date guard from 2027-08-01), the bottles already built stay frozen in
the release, and command-line tools come only from MacPorts and mise. Casks keep working through mycask and
`cask.json`. When a cask's newest version drops Intel, mycask sees it in the app's own `Info.plist` / `lipo` output,
refuses the update and keeps the installed version. For an app that matters, `mycask pin <token>`, or put a
definition that still points at an Intel download in `~/.config/mycask/casks/<token>.json`.
