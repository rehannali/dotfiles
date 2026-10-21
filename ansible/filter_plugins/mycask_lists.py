"""mycask_lists: what an Intel Mac asks mycask (tools/mycask) for, worked out from packages.yml.

    tool_plan.brew | mycask_formulae            formulae.txt: the brew formulae, tap formulae left out
    tool_plan.brew | mycask_cli_map             cli-map.json: {formula: {"port": name} or {"mise": id}}
    casks | mycask_casks(appdir)                casks.txt lines: "token", or "token --appdir=DIR" for appdir: true
    tool_plan.brew | mycask_unsupported(casks)  tap formulae and tap casks, which mycask can't read

mycask reads homebrew/core and homebrew/cask only, so tap entries (owner/tap/name) are reported, not listed.
The map gives a formula its MacPorts `port`, unless MacPorts would have to compile it (`port_build`), else its
`mise_fallback`; mycask turns to it when there is no bottle (`intel_prefer: true`: even when there is one).
"""

import json
import re

SAFE_WORD = re.compile(r"^[\w@%+=:,./~-]+$")


def _tap(name):
    return "/" in str(name)


def mycask_formulae(brew):
    return [b["name"] for b in brew if not _tap(b["name"])]


def mycask_cli_map(brew):
    out = {}
    for b in brew:
        if _tap(b["name"]):
            continue
        if b.get("port") and not b.get("port_build"):
            entry = {"port": b["port"]}
        elif b.get("mise_fallback"):
            entry = {"mise": b["mise_fallback"]}
        else:
            continue
        if b.get("prefer"):
            entry["prefer"] = True
        out[b["name"]] = entry
    return out


def mycask_casks(casks, appdir):
    lines = []
    for c in casks:
        if _tap(c["cask"]):
            continue
        if c.get("appdir"):
            folder = appdir if SAFE_WORD.match(appdir) else json.dumps(appdir)
            lines.append("%s --appdir=%s" % (c["cask"], folder))
        else:
            lines.append(c["cask"])
    return lines


def mycask_unsupported(brew, casks):
    return [b["name"] for b in brew if _tap(b["name"])] + [c["cask"] for c in casks if _tap(c["cask"])]


class FilterModule:
    def filters(self):
        return {"mycask_formulae": mycask_formulae, "mycask_cli_map": mycask_cli_map, "mycask_casks": mycask_casks,
                "mycask_unsupported": mycask_unsupported}
