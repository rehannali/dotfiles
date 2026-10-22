"""Is every package id in packages.yml real? Asks each store for every id and prints what it found.

    python tests/apps_check.py [--markdown FILE]      (needs PyYAML and the internet; CI runs it)

  cask      https://formulae.brew.sh/api/cask/<token>.json        (homebrew/cask; tap casks are checked at install)
  brew      https://formulae.brew.sh/api/formula/<name>.json      (homebrew/core; tap formulae likewise)
  mas       https://itunes.apple.com/lookup?id=<id>               (the App Store, any country's store)
  flatpak   https://flathub.org/api/v2/appstream/<id>             (Flathub)
  snap      https://api.snapcraft.io/v2/snaps/info/<name>         (the Snap Store: a stable amd64 build, and its publisher)
  deb       the keyring and .sources URLs of a vendor apt repository, and the package in its index
  github    https://api.github.com/repos/<repo>/releases/latest   (an asset matching `asset`; GITHUB_TOKEN if set)
  apt       apt-cache show <name>                                 (where apt-cache exists, e.g. the Ubuntu runner; only
                                                                  tools without a mise key, the others come from mise)

Exit status 1 if any id was not found. A store that can't be reached at all is reported as such (exit 2), so a
network outage is not mistaken for a wrong id.
"""
import argparse
import re
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


def fetch(url, extra=None):
    """(status, json or None). Retries a few times on network errors and 5xx; 404 is an answer."""
    host = url.split("/")[2]
    headers = {**UA, **(extra or {})}
    if host == "api.github.com" and os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    if DOWN.get(host, 0) >= 3:
        return None, None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as r:
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


def check_github(repo, asset):
    status, data = fetch(f"https://api.github.com/repos/{repo}/releases/latest")
    if status == 200 and data:
        names = [a["name"] for a in data.get("assets", []) if re.search(asset, a["name"])]
        if not names:
            return False, f"release {data.get('tag_name')} has no asset matching {asset}"
        return True, f"{data.get('tag_name')} {names[0]}"
    return (None, "GitHub not reachable") if status is None else (False, f"no release (HTTP {status})")


def check_flatpak(app_id):
    status, data = fetch(f"https://flathub.org/api/v2/appstream/{app_id}")
    if status == 200 and data:
        return True, f"{data.get('name', app_id)} ({data.get('developer_name') or data.get('project_license') or 'Flathub'})"
    return (None, "store not reachable") if status is None else (False, f"not on Flathub (HTTP {status})")


def check_snap(name):
    status, data = fetch(f"https://api.snapcraft.io/v2/snaps/info/{name}?fields=confinement,version,publisher",
                         {"Snap-Device-Series": "16"})
    if status == 200 and data:
        stable = [c for c in data.get("channel-map") or []
                  if c["channel"]["risk"] == "stable" and c["channel"]["architecture"] == "amd64"]
        pub = data.get("snap", {}).get("publisher", {})
        who = pub.get("display-name", "?") + (" (verified)" if pub.get("validation") == "verified" else "")
        if not stable:
            return False, f"{who}: no stable amd64 build"
        return True, f"{who}, {stable[0].get('version')} ({stable[0].get('confinement')})"
    return (None, "store not reachable") if status is None else (False, f"not in the Snap Store (HTTP {status})")


def check_deb(deb):
    """The vendor repository is there and lists the package: its .sources file names the repository (URIs, Suites,
    Components), whose Packages index for amd64 must contain the package."""
    try:
        with urllib.request.urlopen(urllib.request.Request(deb["keyring"], headers=UA), timeout=20) as r:
            r.read(1)
        with urllib.request.urlopen(urllib.request.Request(deb["sources"], headers=UA), timeout=20) as r:
            src = r.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code} for the keyring or sources"
    except (urllib.error.URLError, TimeoutError, OSError):
        return None, "repository not reachable"
    field = {k.strip(): v.strip() for k, _, v in (line.partition(":") for line in src.splitlines()) if v}
    uri, suite = field.get("URIs", "").split()[0] if field.get("URIs") else "", field.get("Suites", "").split()[0] if field.get("Suites") else ""
    comp = (field.get("Components", "main").split() or ["main"])[0]
    try:
        with urllib.request.urlopen(f"{uri.rstrip('/')}/dists/{suite}/{comp}/binary-amd64/Packages", timeout=30) as r:
            index = r.read().decode(errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError):
        return None, f"index of {uri} not reachable"
    if f"\nPackage: {deb['package']}\n" in "\n" + index:
        return True, f"{deb['package']} in {uri} {suite}"
    return False, f"{deb['package']} not in {uri} {suite}"


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
        if "snap" in a:
            rows.append((*check_snap(a["snap"]), "snap", a["name"], a["snap"]))
        if "deb" in a:
            rows.append((*check_deb(a["deb"]), "deb", a["name"], a["deb"]["package"]))
        if "github" in a:
            rows.append((*check_github(a["github"], a["asset"]), "github", a["name"], a["github"]))
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
