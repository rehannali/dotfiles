"""private: personal and secret values for the inventory, from Bitwarden, never from the repo.

The repo holds templates only: `{{ private.piserver.ssh_port }}`. This vars plugin gives every host one variable,
`private` ({host: {key: value}}), read once per run from

  1. the file DOTFILES_PRIVATE_FILE (default ~/.config/dotfiles/private.yml), if it exists: outside the repo, mode 600;
     for a machine without Bitwarden. Its layout is ansible/private.example.yml
  2. and Bitwarden, whose fields win over the file's, from the unlocked vault (BW_SESSION: bootstrap.sh --bitwarden and dot unlock it; without it, a
     master password in BW_PASSWORD, or the login bootstrap.sh kept in the Keychain / Secret Service, unlocks the
     vault here, for this run only): one item per
     host, named DOTFILES_PRIVATE_PREFIX + host (default "dotfiles.piserver", like host_vars/piserver.yml), in any
     folder. Each value is a custom field: name ssh_port, value 2222. A name used more than once is a list
     (authorized_keys, one field per key); a boolean field is true / false; every other value is a string. The
     item's notes are not read: they are yours, for comments.

Items can also be named after an inventory group: "dotfiles.all" for what every machine shares (git_name),
"dotfiles.mac_personal" / "dotfiles.mac_work" for a kind of machine. Each host gets `private_host`: the fields of
dotfiles.all, then of its groups (outer ones first: macs, then mac_personal), then of its own item, a later one
winning; so a template needs no host name: {{ private_host.git_email }}.

Neither there: `private` is an empty dict, and only what refers to it fails, with a message saying how to unlock.

Without Bitwarden, environment variables can also come from the file DOTFILES_ENV_FILE (default
~/.config/dotfiles/env): NAME=value lines (ansible/env.example). They are put in this run's environment, over what the
shell had (which came from the previous run), and every name in it is exported in ~/.config/dotfiles/secrets.zsh
(`private_env_names`); a Bitwarden field of the same name still wins.

Fill Bitwarden from a YAML file in that layout (creates the items, replaces the fields of existing ones):

  python3 ansible/vars_plugins/private.py import ~/private.yml
"""

import json
import os
import re
import subprocess
import sys

import yaml

try:
    from ansible.errors import AnsibleError
    from ansible.plugins.vars import BaseVarsPlugin
except ImportError:   # `private.py import` runs without Ansible
    AnsibleError = SystemExit
    BaseVarsPlugin = object

DOCUMENTATION = """
    name: private
    short_description: personal and secret values from Bitwarden (or a private file outside the repo)
    description: Loads a mapping of host to values into the variable `private`, from DOTFILES_PRIVATE_FILE or the
      custom fields of one Bitwarden item per host.
    options:
      stage:
        default: task
        ini:
          - key: stage
            section: vars_private
        env:
          - name: ANSIBLE_VARS_PLUGIN_STAGE
"""

FIELD_TEXT, FIELD_HIDDEN, FIELD_BOOLEAN = 0, 1, 2
SECRET_SUFFIXES = ("_token", "_key", "_password", "_secret", "_profile")
_CACHE = {}


def _prefix():
    return os.environ.get("DOTFILES_PRIVATE_PREFIX", "dotfiles.")


def _bw(*args, stdin=None):
    try:
        out = subprocess.run(["bw", *args], input=stdin, capture_output=True, text=True, timeout=120,
                             env={**os.environ, "BW_NOINTERACTION": "true"})
    except (OSError, subprocess.TimeoutExpired) as e:
        raise AnsibleError("private: could not run the Bitwarden CLI (bw): %s" % e)
    if out.returncode != 0:
        raise AnsibleError("private: bw %s failed: %s" % (args[0], (out.stderr or out.stdout).strip()[:200]))
    return out.stdout


_SECRET_HELPER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "home", ".local", "bin",
                              "dotfiles-secret")


def _unlock():
    """BW_SESSION; else a session from BW_PASSWORD (the vault must be logged in); else from the login bootstrap.sh kept
    in the Keychain / Secret Service (dotfiles-secret bw-session). None of them: the vault stays closed."""
    if not os.environ.get("BW_SESSION") and os.environ.get("BW_PASSWORD"):
        os.environ["BW_SESSION"] = _bw("unlock", "--passwordenv", "BW_PASSWORD", "--raw").strip()
    if not os.environ.get("BW_SESSION") and os.path.isfile(_SECRET_HELPER):
        try:
            out = subprocess.run([_SECRET_HELPER, "bw-session"], capture_output=True, text=True, timeout=120)
            if out.returncode == 0 and out.stdout.strip():
                os.environ["BW_SESSION"] = out.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass
    return bool(os.environ.get("BW_SESSION"))


def _host_items():
    """{host: item} for the items named prefix + host."""
    prefix = _prefix()
    items = json.loads(_bw("list", "items", "--search", prefix.strip()))
    return {item["name"][len(prefix):]: item for item in items
            if item.get("name", "").startswith(prefix) and len(item["name"]) > len(prefix)}


def fields_to_values(fields):
    """Bitwarden custom fields to {name: value}: a repeated name is a list, a boolean field a bool."""
    values = {}
    for field in fields or []:
        name, value = field.get("name"), field.get("value")
        if not name or field.get("type") not in (FIELD_TEXT, FIELD_HIDDEN, FIELD_BOOLEAN):
            continue
        if field.get("type") == FIELD_BOOLEAN:
            value = str(value).lower() == "true"
        if name in values:
            values[name] = (values[name] if isinstance(values[name], list) else [values[name]]) + [value]
        else:
            values[name] = value
    return values


def values_to_fields(values):
    """{name: value} to Bitwarden custom fields: a list becomes one field per element; secrets are hidden fields;
    empty values are left out (a missing key is the same as an empty one)."""
    fields = []
    for name, value in values.items():
        for v in value if isinstance(value, list) else [value]:
            if v is None or v == "":
                continue
            if isinstance(v, bool):
                fields.append({"name": name, "value": str(v).lower(), "type": FIELD_BOOLEAN})
            else:
                kind = FIELD_HIDDEN if name.endswith(SECRET_SUFFIXES) else FIELD_TEXT
                fields.append({"name": name, "value": str(v), "type": kind})
    return fields


def load_private():
    if "data" in _CACHE:
        return _CACHE["data"]
    data, sources = {}, []
    path = os.path.expanduser(os.environ.get("DOTFILES_PRIVATE_FILE", "~/.config/dotfiles/private.yml"))
    if os.path.isfile(path):
        with open(path) as fh:
            data = yaml.safe_load(fh) or {}
        if not isinstance(data, dict):
            raise AnsibleError("private: %s is not a YAML mapping" % path)
        sources.append(path)
    if _unlock():
        try:
            _bw("sync")   # the newest values; offline, the local copy
        except AnsibleError:
            pass
        for host, item in _host_items().items():
            data[host] = {**(data.get(host) or {}), **fields_to_values(item.get("fields"))}
        sources.insert(0, "Bitwarden")
    _CACHE["data"] = data
    _CACHE["source"] = " + ".join(sources) or None
    return data


ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def load_env_file():
    """NAME=value lines of DOTFILES_ENV_FILE into this run's environment, over the shell's; the names."""
    if "env_names" in _CACHE:
        return _CACHE["env_names"]
    names = []
    path = os.path.expanduser(os.environ.get("DOTFILES_ENV_FILE", "~/.config/dotfiles/env"))
    if os.path.isfile(path):
        with open(path) as fh:
            for number, line in enumerate(fh, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[len("export "):].lstrip()
                name, sep, value = line.partition("=")
                name, value = name.strip(), value.strip()
                if not sep or not ENV_NAME.match(name):
                    raise AnsibleError("private: %s line %d is not NAME=value" % (path, number))
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                    value = value[1:-1]
                os.environ[name] = value
                names.append(name)
    _CACHE["env_names"] = names
    return names


def import_file(path):
    """Create or update one item per host (prefix + host), from a YAML file in the private.example.yml layout."""
    if not _unlock():
        raise SystemExit("private: unlock Bitwarden first: export BW_SESSION=$(bw unlock --raw), or BW_PASSWORD")
    with open(os.path.expanduser(path)) as fh:
        data = yaml.safe_load(fh) or {}
    _bw("sync")
    existing = _host_items()
    for host, values in data.items():
        fields = values_to_fields(values or {})
        if host in existing:
            item = json.loads(_bw("get", "item", existing[host]["id"]))
            item["fields"] = fields
            _bw("edit", "item", item["id"], _bw("encode", stdin=json.dumps(item)))
            print("updated %s%s (%d fields)" % (_prefix(), host, len(fields)))
        else:
            item = json.loads(_bw("get", "template", "item"))
            item.update({"type": 2, "secureNote": {"type": 0}, "name": _prefix() + host, "notes": None,
                         "login": None, "fields": fields})
            _bw("create", "item", _bw("encode", stdin=json.dumps(item)))
            print("created %s%s (%d fields)" % (_prefix(), host, len(fields)))


def _uses_private(value):
    if isinstance(value, str):
        return "private." in value
    if isinstance(value, dict):
        return any(_uses_private(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_uses_private(v) for v in value)
    return False


class VarsModule(BaseVarsPlugin):
    """Stage `task` (the default above): runs only for the hosts a play actually uses, so a host that needs the
    private values stops with a clear message when they are not there, and no other host (CI) is affected."""
    REQUIRES_ENABLED = True

    def get_vars(self, loader, path, entities, cache=True):
        super().get_vars(loader, path, entities)
        env_names = load_env_file()
        data = load_private()
        for entity in entities if isinstance(entities, list) else [entities]:
            if entity.name in data or not _uses_private(getattr(entity, "vars", {})):
                continue
            if not _CACHE.get("source"):
                raise AnsibleError(
                    "%s needs the private values (Bitwarden item %r), but Bitwarden is locked and there is no %s. "
                    "Unlock it: export BW_SESSION=$(bw unlock --raw) or BW_PASSWORD, or run through "
                    "bootstrap.sh --bitwarden / dot with bitwarden on (docs/bitwarden.md, 'Private values')."
                    % (entity.name, _prefix() + entity.name,
                       os.environ.get("DOTFILES_PRIVATE_FILE", "~/.config/dotfiles/private.yml")))
            raise AnsibleError("%s needs the private values, but %s has none for it: create the Bitwarden item %r "
                               "(or run bw sync after creating it), docs/bitwarden.md, 'Private values'."
                               % (entity.name, _CACHE["source"], _prefix() + entity.name))
        result = {"private": data, "private_source": _CACHE.get("source") or "", "private_env_names": env_names}
        hosts = [e for e in (entities if isinstance(entities, list) else [entities]) if type(e).__name__ == "Host"]
        if len(hosts) == 1:
            groups = sorted(hosts[0].get_groups(), key=lambda g: g.depth)   # all, macs, mac_personal
            merged = {}
            for name in [g.name for g in groups] + [hosts[0].name]:
                merged.update(data.get(name) or {})
            result["private_host"] = merged
        return result


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "import":
        raise SystemExit("usage: python3 ansible/vars_plugins/private.py import <private.yml>")
    import_file(sys.argv[2])
