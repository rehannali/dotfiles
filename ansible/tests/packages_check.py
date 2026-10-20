"""Checks on inventory/group_vars/all/packages.yml, for every kind of machine.

    python tests/packages_check.py       (needs ansible-core importable and PyYAML)

- the tool_plan filter accepts every entry, and installs each tool with one manager at most
- every cli tool is installed by something on macOS and Linux
- port / mise_fallback only come with a brew formula, and only reach Intel Macs
- the tap trust lists match what is used from taps (Homebrew 6 loads nothing from an untrusted tap)
"""
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "filter_plugins"))
from tool_plan import tool_plan  # noqa: E402

pk = yaml.safe_load(open(os.path.join(os.path.dirname(HERE), "inventory", "group_vars", "all", "packages.yml")))["packages"]
TARGETS = [("Darwin", "arm64"), ("Darwin", "x86_64"), ("Linux", "x86_64")]
bad = []

for t in pk["tools"]:
    for key in ("port", "mise_fallback"):
        if t.get(key) and not t.get("brew"):
            bad.append(f"{t['name']}: {key} is only a fallback for a brew formula")

for system, arch in TARGETS:
    for gui in (True, False):
        plan = tool_plan(pk["tools"], system, arch, gui)
        for t in pk["tools"]:
            names = {"mise": {t.get("mise"), t.get("mise_intel") if isinstance(t.get("mise_intel"), str) else None},
                     "brew": {t.get("brew")}, "apt": {t.get("apt")}}
            hits = [mgr for mgr in ("mise", "brew", "apt")
                    for e in plan[mgr] if (e["name"] if isinstance(e, dict) else e) in names[mgr] - {None}]
            if len(hits) > 1:
                bad.append(f"{t['name']} installed by {hits} on {system}/{arch}")
            if t["kind"] == "cli" and not hits:
                bad.append(f"cli tool {t['name']} is not installed by anything on {system}/{arch}")
        intel = system == "Darwin" and arch == "x86_64"
        for e in plan["brew"]:
            if not intel and (e["port"] or e["mise_fallback"]):
                bad.append(f"{e['name']}: port / mise_fallback set outside an Intel Mac")
        print(f"  {system}/{arch} gui={gui}: " + ", ".join(f"{k}={len(v)}" for k, v in sorted(plan.items())))

trusted, taps = set(), {}
for t in pk["taps"]:
    if not set(t) <= {"name", "formulae", "casks", "needs"}:
        bad.append(f"tap entry {t}: only name, formulae, casks and needs are known")
    if t.get("needs") and not t.get("casks"):
        bad.append(f"tap entry {t['name']}: needs are the dependencies of its casks, it has none")
    taps[t["name"]] = t
    trusted |= {t["name"] + "/" + f for f in t.get("formulae", [])}
used = {x["brew"] for x in pk["tools"] if x.get("brew") and x["brew"].count("/") == 2}
casks = {c["name"] for c in pk["darwin"]["casks"] + pk["darwin_arm"]["casks"]}
for name in sorted(used - trusted):
    bad.append(f"{name} comes from a tap but is not in that tap's formulae list")
for name in sorted(c for c in casks if c.count("/") == 2):
    tap, short = name.rsplit("/", 1)
    if short not in taps.get(tap, {}).get("casks", []):
        bad.append(f"cask {name} comes from a tap but is not in that tap's casks list")
for tap, t in taps.items():
    bad += [f"{tap}/{f} is trusted but no tool uses it" for f in t.get("formulae", []) if f"{tap}/{f}" not in used]
    bad += [f"cask {c} is trusted for {tap} but is not in darwin.casks" for c in t.get("casks", [])
            if c not in casks and f"{tap}/{c}" not in casks]
print(f"  taps: {len(taps)}")

for b in bad:
    print("FAIL:", b)
sys.exit(1 if bad else 0)
