#!/usr/bin/env bash
# Render every chezmoi template for each supported target and lint the results.
#
#   scripts/verify-render.sh [output-dir]
#
# Needs: chezmoi, shellcheck, python3 (and zsh, optionally, for `zsh -n`).
# Nothing is applied: templates are rendered with `chezmoi execute-template`,
# overriding .chezmoi.os / .chezmoi.arch (this also reaches included partials).
set -uo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$(mktemp -d)}"
export HOME="${VERIFY_HOME:-$(mktemp -d)}"   # keep chezmoi away from the real home

# os/arch[/profile]; no profile = full
TARGETS=("darwin/arm64" "darwin/amd64" "linux/amd64" "windows/amd64" "darwin/arm64/cli" "linux/amd64/cli")
# quicker local run on a few targets: VERIFY_TARGETS="linux/amd64 darwin/arm64/cli" scripts/verify-render.sh
if [ -n "${VERIFY_TARGETS:-}" ]; then read -r -a TARGETS <<< "$VERIFY_TARGETS"; fi

# Scripts that must render empty in the cli (server) profile even though the OS would run them.
CLI_EMPTY=" run_onchange_after_10-configure-defaults.sh.tmpl run_onchange_after_13-install-ruby-gems.sh.tmpl run_onchange_after_14-install-flutter.sh.tmpl run_once_after_31-install-xcode-runtime.sh.tmpl "


# Which targets a script must render NON-empty for. Anything not listed must be empty.
declare -A RUNS_ON=(
  [run_once_before_00-utils.sh.tmpl]="darwin linux"
  [run_once_before_01-pre-setup.sh.tmpl]="darwin"
  [run_onchange_before_05-install-apt-packages.sh.tmpl]="linux"
  [run_once_before_10-install-omz.sh.tmpl]="darwin linux"
  [run_onchange_11-install-packages.sh.tmpl]="darwin"
  [run_once_after_00-setup-zsh-theme.sh.tmpl]="darwin linux"
  [run_onchange_after_10-configure-defaults.sh.tmpl]="darwin"
  [run_onchange_after_12-install-mise-tools.sh.tmpl]="darwin linux"
  [run_onchange_after_13-install-ruby-gems.sh.tmpl]="darwin"
  [run_onchange_after_14-install-flutter.sh.tmpl]="darwin linux"
  [run_once_after_30-setup-additional.sh.tmpl]="darwin linux"
  [run_once_after_31-install-xcode-runtime.sh.tmpl]="darwin"
  [run_once_after_90-change-shell.sh.tmpl]="darwin linux"
  [run_onchange_install-winget.ps1.tmpl]="windows"
)

fail=0
bad() { echo "  FAIL: $*"; fail=$((fail + 1)); }

target_os() { echo "${1%%/*}"; }
target_arch() { local r="${1#*/}"; echo "${r%%/*}"; }
target_profile() { local r="${1#*/}"; if [[ "$r" == */* ]]; then echo "${r#*/}"; else echo full; fi; }
override() { # override <target> -> --override-data JSON (email only matters to file templates)
  echo "{\"name\":\"Test User\",\"email\":\"test@example.com\",\"bitwarden\":false,\"profile\":\"$(target_profile "$1")\",\"chezmoi\":{\"os\":\"$(target_os "$1")\",\"arch\":\"$(target_arch "$1")\"}}"
}

render() { # render <target> <template> -> stdout
  chezmoi -S "$SRC" execute-template --override-data "$(override "$1")" < "$2"
}

for target in "${TARGETS[@]}"; do
  os="$(target_os "$target")"
  profile="$(target_profile "$target")"
  dir="$OUT/${target//\//-}"
  mkdir -p "$dir"
  echo "== $target"
  while IFS= read -r tmpl; do
    name="$(basename "$tmpl")"
    out="$dir/${tmpl#"$SRC"/home/}"
    mkdir -p "$(dirname "$out")"
    if ! render "$target" "$tmpl" > "$out" 2> "$out.err"; then
      bad "render error: ${tmpl#"$SRC"/} -> $(head -c 300 "$out.err")"
      continue
    fi
    [ -s "$out.err" ] || rm -f "$out.err"
    nonempty=false
    grep -q '[^[:space:]]' "$out" && nonempty=true

    if [[ -n "${RUNS_ON[$name]+x}" ]]; then
      if [[ " ${RUNS_ON[$name]} " == *" $os "* ]] && ! { [ "$profile" = cli ] && [[ "$CLI_EMPTY" == *" $name "* ]]; }; then
        $nonempty || bad "$name should render for $target but is empty"
      else
        $nonempty && bad "$name must render empty on $target"
      fi
    fi
    if [ "$profile" = cli ] && [ "$name" = run_onchange_11-install-packages.sh.tmpl ] && grep -qE '^(cask|mas) ' "$out"; then
      bad "cli profile still has casks / App Store apps in the Brewfile on $target"
    fi

    $nonempty || continue
    case "$name" in
      *.sh.tmpl)
        bash -n "$out" || bad "bash -n: $name"
        # SC1090/SC1091: the sourced utils file is generated at apply time.
        # SC2154: the helper functions come from that same file.
        shellcheck -s bash -e SC1090,SC1091 "$out" > "$out.shellcheck" 2>&1 \
          || { bad "shellcheck: $name"; sed 's/^/      /' "$out.shellcheck" | head -20; }
        ;;
      dot_zshenv.tmpl | dot_zprofile.tmpl | dot_zshrc.tmpl)
        if command -v zsh > /dev/null 2>&1; then zsh -n "$out" || bad "zsh -n: $name"; fi
        ;;
    esac
  done < <(find "$SRC/home" -name '*.tmpl' -not -name '.chezmoi.toml.tmpl' -not -path '*/.git/*' -not -path '*/themes/*' | sort)

  # The config template is the only place that may prompt; the DOTFILES_* variables must make it non-interactive.
  for want in full cli; do
    cfg_out="$(DOTFILES_NAME="Test User" DOTFILES_EMAIL=test@example.com DOTFILES_PROFILE=$want DOTFILES_BITWARDEN=false \
      chezmoi -S "$SRC" execute-template --init < "$SRC/home/.chezmoi.toml.tmpl" 2>&1)" \
      || bad ".chezmoi.toml.tmpl failed for profile $want: $cfg_out"
    [[ "$cfg_out" == *'name = "Test User"'* && "$cfg_out" == *'email = "test@example.com"'* \
      && "$cfg_out" == *"profile = \"$want\""* && "$cfg_out" == *"bitwarden = false"* ]] \
      || bad ".chezmoi.toml.tmpl did not honor the DOTFILES_* variables for profile $want: $cfg_out"
  done
  cfg_out="$(DOTFILES_NAME=x DOTFILES_EMAIL=x@y.z DOTFILES_PROFILE=full DOTFILES_BITWARDEN=true \
    chezmoi -S "$SRC" execute-template --init < "$SRC/home/.chezmoi.toml.tmpl" 2>&1)"
  [[ "$cfg_out" == *'unlock = "auto"'* ]] || bad "Bitwarden enabled but chezmoi's unlock = auto is missing"
  if DOTFILES_NAME=x DOTFILES_EMAIL=x@y.z DOTFILES_PROFILE=bogus DOTFILES_BITWARDEN=false chezmoi -S "$SRC" \
      execute-template --init < "$SRC/home/.chezmoi.toml.tmpl" > /dev/null 2>&1; then bad ".chezmoi.toml.tmpl accepted profile 'bogus'"; fi

  # mise config must be valid TOML and agree with the tool plan.
  cfg="$dir/dot_config/mise/config.toml.tmpl"
  if [ -s "$cfg" ]; then
    python3 - "$cfg" << 'PY' || bad "mise config invalid for $target"
import sys, tomllib
cfg = tomllib.load(open(sys.argv[1], "rb"))
tools = cfg.get("tools", {})
assert tools, "no [tools]"
for rt in ("node", "python", "ruby", "java", "go", "rust", "uv"):
    assert rt in tools, f"runtime {rt} missing"
print(f"  mise config: {len(tools)} tools ({len(tools) - 7} CLI)")
PY
  fi
done

# One manager per tool, per target (policy: never brew AND mise for the same tool).
render_str() { # render_str <target> '<template text>'
  chezmoi -S "$SRC" execute-template --override-data "$(override "$1")" "$2"
}
for target in "${TARGETS[@]}"; do
  plan="$(render_str "$target" '{{ includeTemplate "tool-plan" . }}')" || { bad "tool-plan failed for $target"; continue; }
  tools="$(render_str "$target" '{{ .packages.tools | toJson }}')"
  python3 - "$target" "$plan" "$tools" << 'PY' || bad "plan invariant broken for $target"
import json, sys
target, plan, tools = sys.argv[1], json.loads(sys.argv[2]), json.loads(sys.argv[3])
for t in tools:
    assert not t.get("port") or t.get("brew"), f"{t['name']}: port is only a fallback for a brew formula"
    names = {"mise": [t.get("mise"), t.get("mise_intel") if isinstance(t.get("mise_intel"), str) else None],
             "brew": [t.get("brew")], "apt": [t.get("apt")]}
    hits = []
    for mgr, entries in plan.items():
        if mgr == "expect":
            continue
        for e in entries:
            val = e["name"] if isinstance(e, dict) else e
            if val is not None and val in names[mgr]:
                hits.append(mgr)
    assert len(hits) <= 1, f"{t['name']} installed by {hits} on {target}"
    if t["kind"] == "cli" and target.split("/")[0] in ("darwin", "linux") and not hits:
        raise SystemExit(f"cli tool {t['name']} is not installed by anything on {target}")
for e in plan["expect"]:
    assert e["via"] in ("mise", "brew", "apt"), e
    assert not e["port"] or target.startswith("darwin/amd64"), f"port set outside an Intel Mac: {e}"
print(f"  {target}: " + ", ".join(f"{k}={len(v)}" for k, v in sorted(plan.items())))
PY
done

# Homebrew 6 refuses formulae and casks from taps that are not trusted: every formula or cask used from a tap has
# to be listed under that tap in packages.yml (that list is what gets trusted), and nothing listed may be unused.
packages="$(render_str darwin/arm64 '{{ .packages | toJson }}')" || bad "could not render packages for the tap check"
python3 - "$packages" << 'PY' || bad "tap trust list does not match what is used from taps"
import json, sys
pk = json.loads(sys.argv[1])
trusted = {"formula": set(), "cask": set()}
taps = {}
for t in pk["taps"]:
    assert set(t) <= {"name", "formulae", "casks", "needs"}, f"tap entry {t}: only name, formulae, casks and needs are known"
    assert not t.get("needs") or t.get("casks"), f"tap entry {t['name']}: needs are the dependencies of its casks, it has none"
    taps[t["name"]] = t
    trusted["formula"] |= {t["name"] + "/" + f for f in t.get("formulae", [])}
used_formulae = {x["brew"] for x in pk["tools"] if x.get("brew") and x["brew"].count("/") == 2}
casks = {c["name"] for c in pk["darwin"]["casks"] + pk["darwin_arm"]["casks"]}
for name in sorted(used_formulae):
    assert name in trusted["formula"], f"{name} comes from a tap but is not in that tap's formulae list"
for name in sorted(c for c in casks if c.count("/") == 2):
    assert name.rsplit("/", 1)[0] in taps and name.rsplit("/", 1)[1] in taps[name.rsplit("/", 1)[0]].get("casks", []), \
        f"cask {name} comes from a tap but is not in that tap's casks list"
for tap, t in taps.items():
    for f in t.get("formulae", []):
        assert tap + "/" + f in used_formulae, f"{tap}/{f} is trusted but no tool uses it"
    for c in t.get("casks", []):
        assert c in casks or tap + "/" + c in casks, f"cask {c} is trusted for {tap} but is not in darwin.casks"
print(f"  taps: {len(taps)}, trusted items: {sum(len(t.get('formulae', [])) + len(t.get('casks', [])) for t in taps.values())}, all used")
PY

# Settings must really change the output (and the defaults must stay what they were), for the templates that read them.
settings_check() { # settings_check <description> <target os> <override-data JSON> <template> <expected substring> [absent]
  local out
  out="$(chezmoi -S "$SRC" execute-template --override-data "$3" < "$SRC/$4" 2>&1)" || { bad "$1: template failed: $out"; return; }
  if [ "${6:-}" = absent ]; then
    if grep -qF -- "$5" <<< "$out"; then bad "$1: found '$5'"; fi
  elif ! grep -qF -- "$5" <<< "$out"; then
    bad "$1: '$5' is missing"
  fi
}
DARWIN='"chezmoi":{"os":"darwin","arch":"arm64","destDir":"/tmp/x","homeDir":"/tmp/x"},"profile":"full"'
WIN='"chezmoi":{"os":"windows","arch":"amd64","destDir":"/tmp/x","homeDir":"/tmp/x"}'
LINUX='"chezmoi":{"os":"linux","arch":"amd64","destDir":"/tmp/x","homeDir":"/tmp/x"}'
DOMAINS=home/dot_config/wezterm/config/domains.lua.tmpl
DEFAULTS=home/.chezmoiscripts/run_onchange_after_10-configure-defaults.sh.tmpl
settings_check "wezterm WSL domain default" windows "{$WIN}" $DOMAINS 'distribution = "Ubuntu"'
settings_check "wezterm WSL domain default has no user" windows "{$WIN}" $DOMAINS 'username' absent
settings_check "wezterm WSL domain user" windows "{$WIN,\"settings\":{\"wsl\":{\"distribution\":\"Debian\",\"username\":\"ada\"}}}" $DOMAINS 'default_cwd = "/home/ada"'
settings_check "macOS dock default" darwin "{$DARWIN}" $DEFAULTS 'orientation" -string "left"'
settings_check "macOS dock custom" darwin "{$DARWIN,\"settings\":{\"macos\":{\"defaults\":true,\"dock\":{\"orientation\":\"bottom\",\"tile_size\":30,\"autohide\":false,\"show_recents\":true}}}}" $DEFAULTS 'tilesize" -int "30"'
settings_check "macOS defaults off renders nothing" darwin "{$DARWIN,\"settings\":{\"macos\":{\"defaults\":false}}}" $DEFAULTS 'defaults write' absent
settings_check "shell env default" linux "{$LINUX}" home/dot_zshenv.tmpl 'export PYTHONUNBUFFERED="1"'
settings_check "shell env and path custom" linux "{$LINUX,\"settings\":{\"shell\":{\"env\":{\"EDITOR\":\"nvim\"},\"path\":[\"\$HOME/a\",\"\$HOME/b\"]}}}" home/dot_zshenv.tmpl 'export EDITOR="nvim"'
settings_check "npm globals from packages.yml" linux "{$LINUX}" home/.chezmoiscripts/run_once_after_30-setup-additional.sh.tmpl 'npm i -g "firebase-tools"'
settings_check "npm globals empty" linux "{$LINUX,\"packages\":{\"npm\":[]}}" home/.chezmoiscripts/run_once_after_30-setup-additional.sh.tmpl 'npm i -g' absent
echo "  settings are honoured (wezterm domain, dock, shell env/path, npm globals)"

# Secrets from Bitwarden: render the template with a stand-in `bw`; with Bitwarden off nothing may be rendered.
stub="$(mktemp -d)"
cat > "$stub/bw" << 'BW'
#!/bin/sh
echo '{"name":"x","notes":"n","login":{"username":"u","password":"it'"'"'s $ecret"},"fields":[{"name":"token","value":"t0k"}]}'
BW
chmod +x "$stub/bw"
secrets_data='{"name":"T","email":"t@e.x","profile":"full","bitwarden":true,"secrets":{"env":{"A":{"item":"i"},"B":{"item":"i","field":"token"}}},"chezmoi":{"os":"linux","arch":"amd64"}}'
got="$(PATH="$stub:$PATH" chezmoi -S "$SRC" execute-template --override-data "$secrets_data" < "$SRC/home/dot_config/dotfiles/private_secrets.zsh.tmpl" 2>&1)"
[[ "$got" == *"export A='it'\\''s \$ecret'"* && "$got" == *"export B='t0k'"* ]] || bad "secrets template output wrong: $got"
off="$(PATH="$stub:$PATH" chezmoi -S "$SRC" execute-template --override-data "${secrets_data/\"bitwarden\":true/\"bitwarden\":false}" < "$SRC/home/dot_config/dotfiles/private_secrets.zsh.tmpl" 2>&1)"
[ -z "${off//[[:space:]]/}" ] || bad "secrets are rendered although Bitwarden is off: $off"
echo "  bitwarden secrets template ok"

# xcode-pick.py: newest release the Mac can run, never a beta, and a runtime that goes with it (tiny made-up data)
pick="$SRC/home/.chezmoitemplates/xcode-pick.py"
pickdata="$(mktemp)"
cat > "$pickdata" << 'JSON'
[
 {"_dateOrder": 5, "version": {"number": "27.2", "release": {"beta": 1}},    "requires": "26.6", "links": {"download": {"architectures": ["arm64"]}}, "sdks": {"iOS": [{"number": "27.2"}]}},
 {"_dateOrder": 4, "version": {"number": "27.1", "release": {"release": true}}, "requires": "26.6", "links": {"download": {"architectures": ["arm64"]}}, "sdks": {"iOS": [{"number": "27.1"}]}},
 {"_dateOrder": 3, "version": {"number": "26.6", "release": {"release": true}}, "requires": "26.2", "links": {"download": {"architectures": ["arm64"]}}, "sdks": {"iOS": [{"number": "26.5"}]}},
 {"_dateOrder": 3, "version": {"number": "26.6", "release": {"release": true}}, "requires": "26.2", "links": {"download": {"architectures": ["arm64", "x86_64"]}}, "sdks": {"iOS": [{"number": "26.5"}]}},
 {"_dateOrder": 1, "version": {"number": "26.3", "release": {"release": true}}, "requires": "15.6", "links": {"download": {"architectures": ["arm64", "x86_64"]}}, "sdks": {"iOS": [{"number": "26.2"}]}}
]
JSON
expect_pick() { # expect_pick <expected> <args...>
  local want="$1"; shift
  local got; got="$(python3 "$pick" "$@" --data "$pickdata" 2> /dev/null)"
  [ "$got" = "$want" ] || bad "xcode-pick.py $* gave '$got', expected '$want'"
}
expect_pick 27.1 xcode --macos 26.6 --arch arm64      # newest release, not the 27.2 beta
expect_pick 26.6 xcode --macos 26.6 --arch x86_64     # 27.1 is Apple Silicon only
expect_pick 26.3 xcode --macos 15.7 --arch arm64      # older macOS, older Xcode
expect_pick 26.5 runtime --xcode 26.6 --macos 26.6 --arch x86_64
expect_pick 27.1 runtime --xcode 27.1 --macos 26.6 --arch arm64
expect_pick ""   runtime --xcode 27.1 --macos 26.6 --arch x86_64   # that Xcode can't run on this Mac
listed_intel="$(mktemp)"; listed_arm="$(mktemp)"
printf '%s\n' "26.3 (17C529) [Universal]" "26.6 (17F113) [Universal] (Installed)" > "$listed_intel"
printf '%s\n' "26.6 (17F113) [Apple Silicon]" "27.1 (27A9275) [Apple Silicon]" "27.2 Beta 3 (27B5038j) [Apple Silicon]" > "$listed_arm"
expect_pick 26.6 xcode --macos 26.6 --arch x86_64 --listed "$listed_intel"
expect_pick 27.1 xcode --macos 26.6 --arch arm64 --listed "$listed_arm"      # the beta row is ignored
expect_pick 26.3 xcode --macos 26.6 --arch x86_64 --listed <(printf '26.3 (17C529) [Universal]\n')   # xcodes lists less
expect_pick 27.1 xcode --macos 26.6 --arch arm64 --listed /nonexistent        # unusable list: release data alone
echo "  xcode-pick.py ok"

echo "rendered into $OUT"
if [ "$fail" -gt 0 ]; then echo "$fail check(s) FAILED"; exit 1; fi
echo "all checks passed"
