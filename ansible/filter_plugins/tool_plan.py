"""tool_plan: which package manager installs each tool on a machine.

    tools | tool_plan(platform, managers, gui_apps)

platform is macos_arm64, macos_x86_64 or debian; managers is that platform's entry of platform_managers
(inventory/group_vars/all/platforms.yml): {cli: brew|mise, system: brew|apt|port|none}. `none` (a platform without a
package list yet, e.g. Fedora): system tools are left out and reported.

    kind cli (or any entry with a mise key)   managers.cli first, then mise, then managers.system
    kind system / apple                       managers.system
    kind apple                                macOS with gui_apps only

On an Intel Mac a brew entry carries its `port` and `mise_fallback`: the packages role tries them, in that order, when
there is no bottle. With `system: port` the port is used directly, else the mise_fallback, else the tool is reported in
`unplanned`. `port_build` lets MacPorts compile the port itself (its dependencies still come as binary archives); such
ports are also listed in `port_build`, and `port_fallback` maps a port to its mise_fallback. `mise_intel` picks another mise id on Intel Macs (or `false`: mise has no Intel build at all).
Exactly one manager per tool, so nothing is ever installed twice.
"""

from ansible.errors import AnsibleFilterError

KINDS = ("cli", "system", "apple")
MANAGERS = ("brew", "mise", "apt", "port")


def tool_plan(tools, platform, managers, gui_apps=True):
    is_mac = str(platform).startswith("macos")
    intel_mac = platform == "macos_x86_64"
    cli, system = managers.get("cli"), managers.get("system")
    if cli not in ("brew", "mise") or system not in ("brew", "apt", "port", "none"):
        raise AnsibleFilterError("platform_managers[%s]: cli must be brew or mise, system brew, apt, port or none (got %r)"
                                 % (platform, managers))
    plan = {"apt": [], "brew": [], "mise": [], "port": [], "port_build": [], "port_fallback": {}, "expect": [], "unplanned": []}
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
            if "mise" not in t or (intel_mac and mise_intel is False):
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

        if via == "brew":
            plan["brew"].append({
                "name": ident,
                "prebuilt": t.get("prebuilt") is True,
                "service": t.get("brew_service") is True,
                "source": mise_intel is False,
                "port": str(t.get("port", "")) if intel_mac else "",
                "port_build": intel_mac and t.get("port_build") is True,
                "mise_fallback": str(t.get("mise_fallback", "")) if intel_mac else "",
            })
        elif via:
            plan[via].append(ident)
            if via == "port" and t.get("port_build") is True:
                plan["port_build"].append(ident)
            if via == "port" and t.get("mise_fallback"):
                plan["port_fallback"][ident] = str(t["mise_fallback"])
        elif system == "none" or any(k in t for k in (("brew", "port", "mise", "mise_fallback") if is_mac else ("apt", "mise"))):
            plan["unplanned"].append(t["name"])   # meant for this kind of OS, but no manager here has it

        if via:
            bin_ = t.get("bin", "" if kind == "system" else t["name"])
            on_intel_brew = intel_mac and via == "brew"
            plan["expect"].append({"name": t["name"], "kind": kind, "via": via, "bin": bin_, "source": mise_intel is False,
                                   "port": str(t.get("port", "")) if on_intel_brew else "",
                                   "mise_fallback": str(t.get("mise_fallback", "")) if intel_mac and via in ("brew", "port")
                                   else ""})
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
