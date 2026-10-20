"""The tool_plan filter must decide exactly like chezmoi's tool-plan template while both read packages.yml.

    python tests/tool_plan_parity.py        (needs ansible-core importable, PyYAML, and chezmoi on PATH)
"""
import json
import os
import subprocess
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "filter_plugins"))
from tool_plan import tool_plan  # noqa: E402

TARGETS = [  # (ansible system, ansible architecture, gui_apps) -> chezmoi os/arch/profile
    ("Darwin", "arm64", True, "darwin", "arm64", "full"),
    ("Darwin", "x86_64", True, "darwin", "amd64", "full"),
    ("Linux", "x86_64", True, "linux", "amd64", "full"),
    ("Darwin", "arm64", False, "darwin", "arm64", "cli"),
    ("Darwin", "x86_64", False, "darwin", "amd64", "cli"),
    ("Linux", "x86_64", False, "linux", "amd64", "cli"),
]
BREW_KEYS = ("name", "prebuilt", "source", "port", "mise_fallback")
EXPECT_KEYS = ("name", "kind", "via", "bin")

tools = yaml.safe_load(open(os.path.join(REPO, "home", ".chezmoidata", "packages.yml")))["packages"]["tools"]
bad = 0
for system, arch, gui, os_, carch, profile in TARGETS:
    mine = tool_plan(tools, system, arch, gui)
    data = json.dumps({"profile": profile, "chezmoi": {"os": os_, "arch": carch}})
    ref = json.loads(subprocess.check_output(
        ["chezmoi", "-S", REPO, "execute-template", "--override-data", data, '{{ includeTemplate "tool-plan" . }}']))
    same = (mine["apt"] == ref["apt"] and mine["mise"] == ref["mise"]
            and [[b[k] for k in BREW_KEYS] for b in mine["brew"]] == [[b[k] for k in BREW_KEYS] for b in ref["brew"]]
            and [[e[k] for k in EXPECT_KEYS] for e in mine["expect"]] == [[e[k] for k in EXPECT_KEYS] for e in ref["expect"]])
    print("%-6s %-7s gui=%-5s %s" % (system, arch, gui, "same" if same else "DIFFERENT"))
    bad += not same
sys.exit(1 if bad else 0)
