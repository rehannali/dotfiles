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

TARGETS=("darwin/arm64" "darwin/amd64" "linux/amd64" "windows/amd64")

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
  [run_once_after_30-setup-additional.sh.tmpl]="darwin linux"
  [run_once_after_31-install-xcode-runtime.sh.tmpl]="darwin"
  [run_once_after_90-change-shell.sh.tmpl]="darwin linux"
  [run_onchange_install-winget.ps1.tmpl]="windows"
)

fail=0
bad() { echo "  FAIL: $*"; fail=$((fail + 1)); }

render() { # render <os/arch> <template> -> stdout
  local os="${1%/*}" arch="${1#*/}" init=()
  # --init hides .chezmoidata, so only use it for templates that prompt (dot_gitconfig.tmpl)
  if grep -qE 'prompt(String|Bool|Int|Choice)' "$2" 2> /dev/null; then init=(--init --promptString email=test@example.com); fi
  chezmoi -S "$SRC" execute-template "${init[@]}" \
    --override-data "{\"chezmoi\":{\"os\":\"$os\",\"arch\":\"$arch\"}}" < "$2"
}

for target in "${TARGETS[@]}"; do
  os="${target%/*}"
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
      if [[ " ${RUNS_ON[$name]} " == *" $os "* ]]; then
        $nonempty || bad "$name should render for $target but is empty"
      else
        $nonempty && bad "$name must render empty on $target"
      fi
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
  done < <(find "$SRC/home" -name '*.tmpl' -not -path '*/.git/*' -not -path '*/themes/*' | sort)

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
render_str() { # render_str <os/arch> '<template text>'
  chezmoi -S "$SRC" execute-template \
    --override-data "{\"chezmoi\":{\"os\":\"${1%/*}\",\"arch\":\"${1#*/}\"}}" "$2"
}
for target in "${TARGETS[@]}"; do
  plan="$(render_str "$target" '{{ includeTemplate "tool-plan" . }}')" || { bad "tool-plan failed for $target"; continue; }
  tools="$(render_str "$target" '{{ .packages.tools | toJson }}')"
  python3 - "$target" "$plan" "$tools" << 'PY' || bad "plan invariant broken for $target"
import json, sys
target, plan, tools = sys.argv[1], json.loads(sys.argv[2]), json.loads(sys.argv[3])
for t in tools:
    names = {"mise": t.get("mise"), "brew": t.get("brew"), "apt": t.get("apt")}
    hits = []
    for mgr, entries in plan.items():
        for e in entries:
            val = e["name"] if isinstance(e, dict) else e
            if names[mgr] is not None and val == names[mgr]:
                hits.append(mgr)
    assert len(hits) <= 1, f"{t['name']} installed by {hits} on {target}"
    if t["kind"] == "cli" and target.split("/")[0] in ("darwin", "linux") and not hits:
        raise SystemExit(f"cli tool {t['name']} is not installed by anything on {target}")
print(f"  {target}: " + ", ".join(f"{k}={len(v)}" for k, v in sorted(plan.items())))
PY
done

echo "rendered into $OUT"
if [ "$fail" -gt 0 ]; then echo "$fail check(s) FAILED"; exit 1; fi
echo "all checks passed"
