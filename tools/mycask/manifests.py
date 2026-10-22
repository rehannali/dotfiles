#!/usr/bin/env python3
"""Write the cask lists CI checks, from ansible/inventory/group_vars/all/packages.yml.

    python3 tools/mycask/manifests.py           write intel/casks.txt (mycask) and arm64/casks.txt (Homebrew)
    python3 tools/mycask/manifests.py --check   exit 1 if the committed files differ from packages.yml

They cover every Mac group in the inventory (what any Mac could ask for), so .github/workflows/casks-verify.yml checks
every cask any of them gets: on an Intel Mac with mycask, on Apple Silicon with Homebrew. Tap casks are left out of
both (mycask can't read taps; on Apple Silicon a tap is trusted by the playbook first). A machine's own list is written by Ansible from its bundles, with the same filter
(ansible/filter_plugins/mycask_lists.py). Needs PyYAML: use the Python Ansible runs on if python3 lacks it.
"""
import os
import sys

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is missing; run this with the Python Ansible uses, e.g.\n"
             '  "$(head -1 "$(command -v ansible-playbook)" | cut -c3-)" tools/mycask/manifests.py')

HERE = os.path.dirname(os.path.abspath(__file__))
ANSIBLE = os.path.join(os.path.dirname(os.path.dirname(HERE)), "ansible")
OUT = HERE
sys.path.insert(0, os.path.join(ANSIBLE, "filter_plugins"))
from mycask_lists import mycask_casks  # noqa: E402
from tool_plan import select_bundles  # noqa: E402

HEADER = ("# Written by tools/mycask/manifests.py from ansible/inventory/group_vars/all/packages.yml: every Mac group,\n"
          "# as %s. Edit packages.yml and run the script again, not this file.\n")


def load(*parts):
    with open(os.path.join(ANSIBLE, "inventory", *parts)) as fh:
        return yaml.safe_load(fh) or {}


def manifests():
    gv_all = load("group_vars", "all", "main.yml")
    packages = load("group_vars", "all", "packages.yml")["packages"]
    mac_groups = sorted((load("hosts.yml")["all"]["children"]["macs"].get("children") or {}).keys())
    apps = []
    for group in mac_groups:
        path = os.path.join(ANSIBLE, "inventory", "group_vars", group + ".yml")
        gv = {**gv_all, **(load("group_vars", group + ".yml") if os.path.exists(path) else {})}
        sel = select_bundles(packages["bundles"], gv["bundles"])
        apps += [a for a in sel["apps"] if a not in apps]
    appdir = (gv_all.get("settings_override", {}).get("macos", {}).get("cask_appdir")
              or load("group_vars", "all", "settings.yml")["settings_defaults"]["macos"]["cask_appdir"])
    out = {}
    for folder, arch, label in (("intel", "x86_64", "an Intel Mac (mycask)"), ("arm64", "arm64", "an Apple Silicon Mac (Homebrew)")):
        casks = mycask_casks([a for a in apps if "cask" in a and a.get("arch", arch) == arch], appdir)
        out[folder + "/casks.txt"] = HEADER % label + "\n".join(sorted(casks)) + "\n"
    return out


def main(check=False):
    stale = []
    for name, text in manifests().items():
        path = os.path.join(OUT, name)
        old = open(path).read() if os.path.exists(path) else None
        if old == text:
            continue
        stale.append(name)
        if not check:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as fh:
                fh.write(text)
    if check and stale:
        print("tools/mycask/ cask lists are out of date (%s): run python3 tools/mycask/manifests.py" % ", ".join(stale))
        return 1
    print(("up to date" if not stale else "wrote " + ", ".join(stale)) if not check else "tools/mycask/ cask lists are up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main(check="--check" in sys.argv[1:]))
