"""Checks on the package data, for every kind of machine in the inventory.

    python tests/packages_check.py       (needs ansible-core importable and PyYAML)

- every group's bundles exist, and the tool_plan filter accepts what they select
- each tool is installed by one manager at most; every cli tool by something; nothing a machine is meant to have is
  left without a manager on today's platforms (Apple Silicon, Intel Mac, Debian on x86_64 and arm64)
- port_build, port_select and port_links only come with a port; download is a URL
- every app has a cask, an App Store id, a flatpak id or a GitHub release; flatpak ids look like ids
- every tap formula or cask in use is listed under its tap, and every listed one is used
"""
import os
import re
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "filter_plugins"))
from tool_plan import select_bundles, tool_plan  # noqa: E402

GV = os.path.join(ROOT, "inventory", "group_vars")
pk = yaml.safe_load(open(os.path.join(GV, "all", "packages.yml")))["packages"]
managers = yaml.safe_load(open(os.path.join(GV, "all", "platforms.yml")))["platform_managers"]
main = yaml.safe_load(open(os.path.join(GV, "all", "main.yml")))
bundles = pk["bundles"]
bad = []

# which platforms each group runs on
GROUP_PLATFORMS = {"mac_personal": ["macos_arm64", "macos_x86_64"], "mac_work": ["macos_arm64", "macos_x86_64"],
                   "servers": ["debian"], "wsl": ["debian"], "linux_desktop": ["debian"]}
all_tools = [t for b in bundles.values() for t in b.get("tools") or []]
all_apps = [a for b in bundles.values() for a in b.get("apps") or []]

for t in all_tools:
    if "brew_service" in t and (t["brew_service"] is not True or not t.get("brew")):
        bad.append(f"{t['name']}: brew_service is true or absent, and needs a brew formula")
    if "port_build" in t and (t["port_build"] is not True or not t.get("port")):
        bad.append(f"{t['name']}: port_build is true or absent, and needs a port")
    if "port_select" in t and (not t.get("port") or not isinstance(t["port_select"], list) or len(t["port_select"]) != 2):
        bad.append(f"{t['name']}: port_select is [group, choice] and needs a port")
    if "port_links" in t and (not t.get("port") or not isinstance(t["port_links"], dict)):
        bad.append(f"{t['name']}: port_links is {{command: path}} and needs a port")
    if "download" in t and not str(t["download"]).startswith("https://"):
        bad.append(f"{t['name']}: download is an https URL")
    for gone in ("intel_prefer", "prefer"):
        if gone in t:
            bad.append(f"{t['name']}: {gone} is no longer used")
for a in all_apps:
    if not any(k in a for k in ("cask", "mas", "flatpak", "github")):
        bad.append(f"app {a['name']}: needs a cask, mas, flatpak or github id")
    if "github" in a and (not a.get("asset") or not str(a.get("app", "")).endswith(".app") or "cask" in a):
        bad.append(f"app {a['name']}: a github app needs asset and app (Name.app), and no cask")
    if "macbook" in a and (a["macbook"] is not True or "github" not in a):
        bad.append(f"app {a['name']}: macbook is true or absent, and only for github apps")
    if "flatpak" in a and not re.match(r"^[A-Za-z0-9_-]+(\.[A-Za-z0-9_-]+){2,}$", a["flatpak"]):
        bad.append(f"app {a['name']}: flatpak id {a['flatpak']!r} does not look like one (org.example.App)")
names = [x["name"] for x in all_tools + all_apps]
bad += [f"{n} is in more than one bundle" for n in sorted({n for n in names if names.count(n) > 1})]

for group, platforms in GROUP_PLATFORMS.items():
    gv = {**main, **(yaml.safe_load(open(os.path.join(GV, f"{group}.yml"))) or {})}
    try:
        sel = select_bundles(bundles, gv["bundles"])
    except Exception as e:  # unknown bundle
        bad.append(f"{group}: {e}")
        continue
    for platform in platforms:
        plan = tool_plan(sel["tools"], platform, managers[platform], gv.get("gui_apps", True))
        for t in sel["tools"]:
            ids = {"mise": {t.get("mise"), t.get("mise_intel") if isinstance(t.get("mise_intel"), str) else None,
                            t.get("mise_fallback")},
                   "brew": {t.get("brew")}, "apt": {t.get("apt")}, "port": {t.get("port")}}
            hits = [m for m in ("mise", "brew", "apt", "port")
                    for e in plan[m] if (e["name"] if isinstance(e, dict) else e) in ids[m] - {None}]
            if len(hits) > 1:
                bad.append(f"{group}/{platform}: {t['name']} installed by {hits}")
            if t["kind"] == "cli" and not hits:
                bad.append(f"{group}/{platform}: cli tool {t['name']} is not installed by anything")
        if plan["unplanned"]:
            bad.append(f"{group}/{platform}: no manager for {plan['unplanned']}")
        apps = [a for a in sel["apps"] if any(k in a for k in managers[platform]["apps"])]
        print(f"  {group:14} {platform:13} bundles={len(gv['bundles'])} " + ", ".join(
            f"{k}={len(v)}" for k, v in sorted(plan.items()) if k != "unplanned") + f", apps={len(apps)}"
            + f", runtimes={len(sel['runtimes'])}")

trusted, taps = set(), {}
for t in pk["taps"]:
    if not set(t) <= {"name", "formulae", "casks"}:
        bad.append(f"tap entry {t}: only name, formulae and casks are known")
    taps[t["name"]] = t
    trusted |= {t["name"] + "/" + f for f in t.get("formulae", [])}
used = {x["brew"] for x in all_tools if x.get("brew") and x["brew"].count("/") == 2}
casks = {a["cask"] for a in all_apps if "cask" in a}
for name in sorted(used - trusted):
    bad.append(f"{name} comes from a tap but is not in that tap's formulae list")
for name in sorted(c for c in casks if c.count("/") == 2):
    tap, short = name.rsplit("/", 1)
    if short not in taps.get(tap, {}).get("casks", []):
        bad.append(f"cask {name} comes from a tap but is not in that tap's casks list")
for tap, t in taps.items():
    bad += [f"{tap}/{f} is trusted but no tool uses it" for f in t.get("formulae", []) if f"{tap}/{f}" not in used]
    bad += [f"cask {c} is trusted for {tap} but no app uses it" for c in t.get("casks", [])
            if c not in casks and f"{tap}/{c}" not in casks]
print(f"  taps: {len(taps)}, bundles: {len(bundles)}, tools: {len(all_tools)}, apps: {len(all_apps)}")

# the cask lists that CI verifies (casks-verify.yml) must match packages.yml
sys.path.insert(0, os.path.join(os.path.dirname(ROOT), "tools", "mycask"))
import manifests  # noqa: E402
if manifests.main(check=True) != 0:
    bad.append("tools/mycask/*/casks.txt do not match packages.yml (run python3 tools/mycask/manifests.py)")

for b in bad:
    print("FAIL:", b)
sys.exit(1 if bad else 0)
