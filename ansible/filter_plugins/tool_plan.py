"""tool_plan: which package manager installs each tool on a machine, from inventory/group_vars/all/packages.yml.

                   cli, or any entry with a mise key      system / apple, no mise key
    Apple Silicon  brew (mise only if there is no brew)   brew
    Intel Mac      mise (brew if mise_intel: false)       brew, bottle-only (fallbacks decided at install time)
    Linux          mise (apt if there is no mise key)     apt

Exactly one manager per tool. gui_apps: false (servers, WSL) drops every kind: apple tool.
"""

from ansible.errors import AnsibleFilterError

KINDS = ("cli", "system", "apple")


def tool_plan(tools, system, arch, gui_apps=True):
    system = str(system).lower()
    apple_silicon = system == "darwin" and arch in ("arm64", "aarch64")
    intel_mac = system == "darwin" and not apple_silicon
    plan = {"apt": [], "brew": [], "mise": [], "expect": []}
    if system not in ("darwin", "linux"):
        return plan
    for t in tools:
        kind = t.get("kind")
        if kind not in KINDS:
            raise AnsibleFilterError("packages.tools %r: kind must be cli, system or apple (got %r)" % (t.get("name"), kind))
        if kind == "cli" and "mise" not in t:
            raise AnsibleFilterError("packages.tools %r: kind cli needs a mise key" % t.get("name"))
        mise_intel = t.get("mise_intel")

        via = ""
        if kind == "apple" and (system != "darwin" or not gui_apps):
            pass
        elif apple_silicon:
            via = "brew" if "brew" in t else "mise" if "mise" in t else ""
        elif intel_mac:
            if "mise" in t and mise_intel is not False:
                via = "mise"
            elif "brew" in t:
                via = "brew"
        else:
            via = "mise" if "mise" in t else "apt" if "apt" in t else ""

        source = mise_intel is False
        if via == "mise":
            ident = t["mise"]
            if intel_mac and isinstance(mise_intel, str):
                ident = mise_intel
            plan["mise"].append(ident)
        elif via == "brew":
            plan["brew"].append({
                "name": t["brew"],
                "prebuilt": t.get("prebuilt") is True,
                "source": source,
                "port": str(t.get("port", "")) if intel_mac else "",
                "mise_fallback": str(t.get("mise_fallback", "")) if intel_mac else "",
            })
        elif via == "apt":
            plan["apt"].append(t["apt"])

        if via:
            bin_ = t.get("bin", "" if kind == "system" else t["name"])
            plan["expect"].append({"name": t["name"], "kind": kind, "via": via, "bin": bin_, "source": source,
                                   "port": str(t.get("port", "")) if intel_mac and via == "brew" else "",
                                   "mise_fallback": str(t.get("mise_fallback", "")) if intel_mac and via == "brew" else ""})
    return plan


class FilterModule:
    def filters(self):
        return {"tool_plan": tool_plan}
