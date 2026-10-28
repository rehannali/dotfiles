"""tool_plan: which package manager installs each tool on a machine.

    tools | tool_plan(platform, managers, gui_apps)

platform is macos_arm64, macos_x86_64 or debian; managers is that platform's entry of platform_managers
(inventory/group_vars/all/platforms.yml): {cli: brew|mise|port, system: brew|apt|port|none}. `none` (a platform
without a package list yet, e.g. Fedora): system tools are left out and reported.

    kind cli (or any entry with a mise key)   managers.cli first, then mise, then managers.system
    kind system / apple                       managers.system
    kind apple                                macOS with gui_apps only

With `system: port` (an Intel Mac, which has no Homebrew) a tool without a port takes its mise_fallback, else its
`download` (a .tgz put in ~/.local/bin), else it is reported in `unplanned`. `port_build` lets MacPorts compile the
port itself (its dependencies still come as binary archives); such ports are also listed in `port_build`,
`port_fallback` maps a port to what replaces it when it does not install (its mise_fallback, else its mise id), `port_select` holds the [group, choice] pairs to `port select`, and
`port_links` the commands to link into ~/.local/bin. `mise_intel` picks another mise id on Intel Macs.
Exactly one manager per tool, so nothing is ever installed twice.
"""

from ansible.errors import AnsibleFilterError

KINDS = ("cli", "system", "apple")
MANAGERS = ("brew", "mise", "apt", "port")


def tool_plan(tools, platform, managers, gui_apps=True):
    is_mac = str(platform).startswith("macos")
    intel_mac = platform == "macos_x86_64"
    cli, system = managers.get("cli"), managers.get("system")
    if cli not in ("brew", "mise", "port") or system not in ("brew", "apt", "port", "none"):
        raise AnsibleFilterError("platform_managers[%s]: cli must be brew, mise or port, system brew, apt, port or none "
                                 "(got %r)" % (platform, managers))
    plan = {"apt": [], "brew": [], "mise": [], "port": [], "port_build": [], "port_fallback": {}, "port_select": [],
            "port_links": {}, "download": [], "expect": [], "unplanned": []}
    for t in tools:
        kind = t.get("kind")
        if kind not in KINDS:
            raise AnsibleFilterError("tool %r: kind must be cli, system or apple (got %r)" % (t.get("name"), kind))
        if kind == "cli" and "mise" not in t:
            raise AnsibleFilterError("tool %r: kind cli needs a mise key" % t.get("name"))
        if kind == "apple" and (not is_mac or not gui_apps):
            continue
        mise_intel = t.get("mise_intel")

        def mise_id():
            if "mise" not in t:
                return None
            return mise_intel if intel_mac and isinstance(mise_intel, str) else t["mise"]

        order = [cli, "mise", system] if (kind == "cli" or "mise" in t) else [system]
        via, ident = "", None
        for mgr in dict.fromkeys(order):
            ident = mise_id() if mgr == "mise" else t.get(mgr)
            if ident:
                via = mgr
                break
        if not via and system == "port" and t.get("mise_fallback"):
            via, ident = "mise", t["mise_fallback"]
        if not via and system == "port" and t.get("download"):
            via, ident = "download", t["download"]

        if via == "brew":
            plan["brew"].append({"name": ident, "prebuilt": t.get("prebuilt") is True,
                                 "service": t.get("brew_service") is True})
        elif via == "download":
            plan["download"].append({"name": t["name"], "url": ident, "bin": t.get("bin", t["name"])})
        elif via:
            plan[via].append(ident)
            if via == "port":
                if t.get("port_build") is True:
                    plan["port_build"].append(ident)
                # when the port does not install (no archive for this macOS): its mise_fallback, else its mise id
                fallback = t.get("mise_fallback") or mise_id()
                if fallback:
                    plan["port_fallback"][ident] = str(fallback)
                if t.get("port_select"):
                    plan["port_select"].append(list(t["port_select"]))
                plan["port_links"].update(t.get("port_links") or {})
        elif system == "none" or any(k in t for k in (("brew", "port", "mise", "mise_fallback", "download") if is_mac
                                                        else ("apt", "mise"))):
            plan["unplanned"].append(t["name"])   # meant for this kind of OS, but no manager here has it

        if via:
            bin_ = t.get("bin", "" if kind == "system" else t["name"])
            # a port tool may end up from mise (its port did not install): the audit accepts that copy
            plan["expect"].append({"name": t["name"], "kind": kind, "via": via, "bin": bin_,
                                   "mise_fallback": plan["port_fallback"].get(ident, "") if via == "port" else ""})
    return plan


BUNDLE_KEYS = {"tools": list, "apps": list, "runtimes": dict, "npm": list, "gems": list}


def select_bundles(bundles, names):
    """Merge the bundles a machine picks into one {tools, apps, runtimes, npm, gems}; unknown names fail."""
    unknown = [n for n in names if n not in bundles]
    if unknown:
        raise AnsibleFilterError("unknown bundle(s) %s; packages.yml has: %s" % (", ".join(unknown), ", ".join(bundles)))
    out = {k: t() for k, t in BUNDLE_KEYS.items()}
    for n in names:
        b = bundles[n] or {}
        extra = set(b) - set(BUNDLE_KEYS)
        if extra:
            raise AnsibleFilterError("bundle %s: unknown key(s) %s" % (n, ", ".join(sorted(extra))))
        for k in ("tools", "apps", "npm", "gems"):
            out[k] += [x for x in b.get(k) or [] if x not in out[k]]
        out["runtimes"].update(b.get("runtimes") or {})
    return out


class FilterModule:
    def filters(self):
        return {"tool_plan": tool_plan, "select_bundles": select_bundles}
