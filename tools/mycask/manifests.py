#!/usr/bin/env python3
"""Write the Intel Mac lists for mycask into tools/mycask/intel/, from ansible/inventory/group_vars/all/packages.yml.

    python3 tools/mycask/manifests.py           write casks.txt, formulae.txt and cli-map.json
    python3 tools/mycask/manifests.py --check   exit 1 if the committed files differ from packages.yml

They cover every Mac group in the inventory (what any Intel Mac could ask for), so the intel-bottles workflow builds
what each of them needs. A machine's own lists are written by Ansible from its bundles, with the same filters
(ansible/filter_plugins/mycask_lists.py). Needs PyYAML: use the Python Ansible runs on if python3 lacks it.
"""
import json
import os
import sys

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is missing; run this with the Python Ansible uses, e.g.\n"
             '  "$(head -1 "$(command -v ansible-playbook)" | cut -c3-)" tools/mycask/manifests.py')

HERE = os.path.dirname(os.path.abspath(__file__))
ANSIBLE = os.path.join(os.path.dirname(os.path.dirname(HERE)), "ansible")
OUT = os.path.join(HERE, "intel")
sys.path.insert(0, os.path.join(ANSIBLE, "filter_plugins"))
from mycask_lists import mycask_casks, mycask_cli_map, mycask_formulae  # noqa: E402
from tool_plan import select_bundles, tool_plan  # noqa: E402

HEADER = ("# Written by tools/mycask/manifests.py from ansible/inventory/group_vars/all/packages.yml: every Mac group,\n"
          "# as an Intel Mac. Edit packages.yml and run the script again, not this file.\n")


def load(*parts):
    with open(os.path.join(ANSIBLE, "inventory", *parts)) as fh:
        return yaml.safe_load(fh) or {}


def manifests():
    gv_all = load("group_vars", "all", "main.yml")
    packages = load("group_vars", "all", "packages.yml")["packages"]
    managers = load("group_vars", "all", "platforms.yml")["platform_managers"]["macos_x86_64"]
    mac_groups = sorted((load("hosts.yml")["all"]["children"]["macs"].get("children") or {}).keys())
    tools, apps, app_store = [], [], False
    for group in mac_groups:
        path = os.path.join(ANSIBLE, "inventory", "group_vars", group + ".yml")
        gv = {**gv_all, **(load("group_vars", group + ".yml") if os.path.exists(path) else {})}
        sel = select_bundles(packages["bundles"], gv["bundles"])
        tools += [t for t in sel["tools"] if t not in tools]
        apps += [a for a in sel["apps"] if a not in apps]
        app_store |= bool(gv.get("install_app_store")) and any("mas" in a and "cask" not in a for a in sel["apps"])
    brew = tool_plan(tools, "macos_x86_64", managers, True)["brew"]
    formulae = mycask_formulae(brew) + (["mas"] if app_store else [])   # mas: the App Store's command line
    casks = mycask_casks([a for a in apps if "cask" in a and a.get("arch", "x86_64") == "x86_64"],
                         gv_all.get("settings_override", {}).get("macos", {}).get("cask_appdir")
                         or load("group_vars", "all", "settings.yml")["settings_defaults"]["macos"]["cask_appdir"])
    cli_map = {"_comment": "formula -> fallback when an Intel Mac has no usable bottle (prefer: even when it has one). "
                           "Written by tools/mycask/manifests.py from packages.yml; edit that, not this file."}
    cli_map.update(dict(sorted(mycask_cli_map(brew).items())))
    return {"formulae.txt": HEADER + "\n".join(sorted(formulae)) + "\n",
            "casks.txt": HEADER + "\n".join(sorted(casks)) + "\n",
            "cli-map.json": json.dumps(cli_map, indent=1) + "\n"}


def main(check=False):
    stale = []
    for name, text in manifests().items():
        path = os.path.join(OUT, name)
        old = open(path).read() if os.path.exists(path) else None
        if old == text:
            continue
        stale.append(name)
        if not check:
            os.makedirs(OUT, exist_ok=True)
            with open(path, "w") as fh:
                fh.write(text)
    if check and stale:
        print("tools/mycask/intel/ is out of date (%s): run python3 tools/mycask/manifests.py" % ", ".join(stale))
        return 1
    print(("up to date" if not stale else "wrote " + ", ".join(stale)) if not check else "tools/mycask/intel/ is up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main(check="--check" in sys.argv[1:]))
