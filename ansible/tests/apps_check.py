"""Is every package id in packages.yml real? Asks each store for every id and prints what it found.

    python tests/apps_check.py [--markdown FILE]      (needs PyYAML and the internet; CI runs it)

  cask      https://formulae.brew.sh/api/cask/<token>.json        (homebrew/cask; tap casks are checked at install)
  brew      https://formulae.brew.sh/api/formula/<name>.json      (homebrew/core; tap formulae likewise)
  mas       https://itunes.apple.com/lookup?id=<id>               (the App Store, any country's store)
  flatpak   https://flathub.org/api/v2/appstream/<id>             (Flathub)
  apt       apt-cache show <name>                                 (where apt-cache exists, e.g. the Ubuntu runner; only
                                                                  tools without a mise key, the others come from mise)

Exit status 1 if any id was not found. A store that can't be reached at all is reported as such (exit 2), so a
network outage is not mistaken for a wrong id.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
pk = yaml.safe_load(open(os.path.join(os.path.dirname(HERE), "inventory", "group_vars", "all", "packages.yml")))["packages"]
UA = {"User-Agent": "dotfiles-apps-check (github.com/rehannali/dotfiles)"}


DOWN = {}   # host -> consecutive network failures; after 3 the host is treated as unreachable


def fetch(url):
    """(status, json or None). Retries a few times on network errors and 5xx; 404 is an answer."""
    host = url.split("/")[2]
    if DOWN.get(host, 0) >= 3:
        return None, None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
                body = r.read()
                DOWN[host] = 0
                try:
                    return r.status, json.loads(body)
                except ValueError:
                    return r.status, None
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 404, None
            if e.code < 500 and e.code != 429:
                return e.code, None
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        time.sleep(2 * (attempt + 1))
    DOWN[host] = DOWN.get(host, 0) + 1
    return None, None


def check_cask(token):
    status, data = fetch(f"https://formulae.brew.sh/api/cask/{token}.json")
    if status == 200 and data:
        if data.get("disabled"):
            return False, "disabled upstream (%s)" % (data.get("disable_date") or "no date")
        names = data.get("name") or [token]
        note = " (deprecated)" if data.get("deprecated") else ""
        return True, f"{names[0]} {data.get('version', '')}{note}".strip()
    return (None, "store not reachable") if status is None else (False, f"not found (HTTP {status})")


def check_formula(name):
    status, data = fetch(f"https://formulae.brew.sh/api/formula/{name}.json")
    if status == 200 and data:
        if data.get("disabled"):
            return False, "disabled upstream"
        return True, f"{data.get('name')} {data.get('versions', {}).get('stable', '')}".strip()
    return (None, "store not reachable") if status is None else (False, f"not found (HTTP {status})")


def check_mas(app_id):
    status, data = fetch(f"https://itunes.apple.com/lookup?id={app_id}&entity=macSoftware")
    if status == 200 and data is not None:
        if data.get("resultCount"):
            r = data["results"][0]
            return True, f"{r.get('trackName')} {r.get('version', '')}".strip()
        # not in the US store: try a second one before calling it missing
        status, data = fetch(f"https://itunes.apple.com/lookup?id={app_id}&entity=macSoftware&country=gb")
        if status == 200 and data and data.get("resultCount"):
            r = data["results"][0]
            return True, f"{r.get('trackName')} {r.get('version', '')} (gb store)".strip()
        return False, "no such App Store app"
    return (None, "store not reachable") if status is None else (False, f"HTTP {status}")


def check_flatpak(app_id):
    status, data = fetch(f"https://flathub.org/api/v2/appstream/{app_id}")
    if status == 200 and data:
        return True, f"{data.get('name', app_id)} ({data.get('developer_name') or data.get('project_license') or 'Flathub'})"
    return (None, "store not reachable") if status is None else (False, f"not on Flathub (HTTP {status})")


def check_apt(name):
    rc = subprocess.run(["apt-cache", "show", name], capture_output=True, text=True)
    if rc.returncode == 0 and rc.stdout.strip():
        version = next((l.split(":", 1)[1].strip() for l in rc.stdout.splitlines() if l.startswith("Version:")), "")
        return True, f"{name} {version}"
    return False, "not in this release's package lists"


rows = []   # (ok, found, kind, entry, id); reordered below for the table
for bundle, b in pk["bundles"].items():
    for a in b.get("apps") or []:
        if "cask" in a:
            if a["cask"].count("/") == 2:
                rows.append((True, "tap cask: checked when it is installed", "cask", a["name"], a["cask"]))
            else:
                rows.append((*check_cask(a["cask"]), "cask", a["name"], a["cask"]))
        if "mas" in a:
            rows.append((*check_mas(a["mas"]), "mas", a["name"], a["mas"]))
        if "flatpak" in a:
            rows.append((*check_flatpak(a["flatpak"]), "flatpak", a["name"], a["flatpak"]))
    for t in b.get("tools") or []:
        if t.get("brew") and t["brew"].count("/") != 2:
            rows.append((*check_formula(t["brew"]), "brew", t["name"], t["brew"]))
        # only apt names a machine really installs with apt: a tool with a mise key comes from mise on Debian
        if t.get("apt") and "mise" not in t and shutil.which("apt-cache"):
            rows.append((*check_apt(t["apt"]), "apt", t["name"], t["apt"]))
# (ok, found, kind, name, id) -> (ok, kind, name, id, found)
rows = [(r[0], r[2], r[3], r[4], r[1]) for r in rows]

ap = argparse.ArgumentParser()
ap.add_argument("--markdown", help="also write a Markdown table here (e.g. $GITHUB_STEP_SUMMARY)")
args = ap.parse_args()

mark = {True: "✅", False: "❌", None: "⚠️"}
lines = ["| | kind | entry | id | found |", "|---|---|---|---|---|"]
lines += [f"| {mark[ok]} | {kind} | {name} | `{ident}` | {found} |" for ok, kind, name, ident, found in rows]
missing = [r for r in rows if r[0] is False]
unreachable = [r for r in rows if r[0] is None]
summary = (f"{len(rows) - len(missing) - len(unreachable)} found, {len(missing)} not found, "
           f"{len(unreachable)} not checked (store unreachable)")
report = "## Package ids in packages.yml\n\n" + summary + "\n\n" + "\n".join(lines) + "\n"
print(report)
if args.markdown:
    with open(args.markdown, "a") as fh:
        fh.write(report + "\n")
for ok, kind, name, ident, found in missing:
    print(f"::error::{kind} {ident} ({name}): {found}")
sys.exit(1 if missing else 2 if unreachable else 0)
