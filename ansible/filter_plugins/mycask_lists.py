"""mycask_lists: the casks an Intel Mac asks mycask (tools/mycask) for, worked out from packages.yml.

    casks | mycask_casks(appdir)      casks.txt lines: "token", or "token --appdir=DIR" for appdir: true
    casks | mycask_unsupported        tap casks (owner/tap/name), which mycask can't read

mycask reads homebrew/cask only, so tap casks are reported, not listed.
"""

import json
import re

SAFE_WORD = re.compile(r"^[\w@%+=:,./~-]+$")


def _tap(name):
    return "/" in str(name)


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


def mycask_unsupported(casks):
    return [c["cask"] for c in casks if _tap(c["cask"])]


class FilterModule:
    def filters(self):
        return {"mycask_casks": mycask_casks, "mycask_unsupported": mycask_unsupported}
