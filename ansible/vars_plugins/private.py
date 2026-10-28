"""private: personal and secret values for the inventory, from Bitwarden, never from the repo.

The repo holds templates only: `{{ private.piserver.ssh_port }}`. This vars plugin gives every host one variable,
`private` ({host: {key: value}}), read once per run from

  1. the file DOTFILES_PRIVATE_FILE (default ~/.config/dotfiles/private.yml), if it exists: outside the repo, mode 600;
     for a machine without Bitwarden. Its layout is ansible/private.example.yml
  2. else Bitwarden, from the unlocked vault (BW_SESSION: bootstrap.sh --bitwarden and dot unlock it): the folder
     DOTFILES_PRIVATE_FOLDER (default "dotfiles private") holds one item per host, named like the host, and each value
     is a custom field of that item: name ssh_port, value 2222. A name used more than once is a list
     (authorized_keys, one field per key); a boolean field is true / false; every other value is a string.

Neither there: `private` is an empty dict, and only what refers to it fails, with a message saying how to unlock.

Fill Bitwarden from a YAML file in that layout (creates the folder and the items, updates the fields of existing ones):

  python3 ansible/vars_plugins/private.py import ~/private.yml
"""

import json
import os
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
      custom fields of the items in a Bitwarden folder.
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


def _folder_name():
    return os.environ.get("DOTFILES_PRIVATE_FOLDER", "dotfiles private")


def _bw(*args, stdin=None):
    try:
        out = subprocess.run(["bw", *args], input=stdin, capture_output=True, text=True, timeout=120,
                             env={**os.environ, "BW_NOINTERACTION": "true"})
    except (OSError, subprocess.TimeoutExpired) as e:
        raise AnsibleError("private: could not run the Bitwarden CLI (bw): %s" % e)
    if out.returncode != 0:
        raise AnsibleError("private: bw %s failed: %s" % (args[0], (out.stderr or out.stdout).strip()[:200]))
    return out.stdout


def _folder_id(create=False):
    name = _folder_name()
    ids = [f["id"] for f in json.loads(_bw("list", "folders", "--search", name)) if f.get("name") == name]
    if ids:
        return ids[0]
    if not create:
        raise AnsibleError("private: Bitwarden has no folder %r. Fill it from a YAML file: python3 "
                           "ansible/vars_plugins/private.py import <file> (docs/bitwarden.md, 'Private values')" % name)
    return json.loads(_bw("create", "folder", _bw("encode", stdin=json.dumps({"name": name}))))["id"]


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
    data = {}
    path = os.path.expanduser(os.environ.get("DOTFILES_PRIVATE_FILE", "~/.config/dotfiles/private.yml"))
    if os.path.isfile(path):
        with open(path) as fh:
            data = yaml.safe_load(fh) or {}
        source = path
        if not isinstance(data, dict):
            raise AnsibleError("private: %s is not a YAML mapping" % path)
    elif os.environ.get("BW_SESSION"):
        items = json.loads(_bw("list", "items", "--folderid", _folder_id()))
        data = {item["name"]: fields_to_values(item.get("fields")) for item in items}
        source = "Bitwarden folder %r" % _folder_name()
    else:
        source = None
    _CACHE["data"] = data
    _CACHE["source"] = source
    return data


def import_file(path):
    """Create or update one item per host in the Bitwarden folder, from a YAML file in the private.example.yml layout."""
    if not os.environ.get("BW_SESSION"):
        raise SystemExit("private: unlock Bitwarden first: export BW_SESSION=$(bw unlock --raw)")
    with open(os.path.expanduser(path)) as fh:
        data = yaml.safe_load(fh) or {}
    _bw("sync")
    folder = _folder_id(create=True)
    existing = {item["name"]: item for item in json.loads(_bw("list", "items", "--folderid", folder))}
    for host, values in data.items():
        fields = values_to_fields(values or {})
        if host in existing:
            item = json.loads(_bw("get", "item", existing[host]["id"]))
            item["fields"] = fields
            _bw("edit", "item", item["id"], _bw("encode", stdin=json.dumps(item)))
            print("updated %s (%d fields)" % (host, len(fields)))
        else:
            item = json.loads(_bw("get", "template", "item"))
            item.update({"type": 2, "secureNote": {"type": 0}, "name": host, "notes": None, "login": None,
                         "folderId": folder, "fields": fields})
            _bw("create", "item", _bw("encode", stdin=json.dumps(item)))
            print("created %s (%d fields)" % (host, len(fields)))


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
        data = load_private()
        if not _CACHE.get("source"):
            for entity in entities if isinstance(entities, list) else [entities]:
                if _uses_private(getattr(entity, "vars", {})):
                    raise AnsibleError(
                        "%s needs the private values (Bitwarden folder %r), but Bitwarden is locked and there is no %s. "
                        "Unlock it: export BW_SESSION=$(bw unlock --raw), or run through bootstrap.sh --bitwarden / dot "
                        "with bitwarden on (docs/bitwarden.md, 'Private values')."
                        % (entity.name, _folder_name(),
                           os.environ.get("DOTFILES_PRIVATE_FILE", "~/.config/dotfiles/private.yml")))
        return {"private": data, "private_source": _CACHE.get("source") or ""}


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "import":
        raise SystemExit("usage: python3 ansible/vars_plugins/private.py import <private.yml>")
    import_file(sys.argv[2])
