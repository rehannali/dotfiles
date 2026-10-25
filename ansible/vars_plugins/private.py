"""private: personal and secret values for the inventory, from Bitwarden, never from the repo.

The repo holds templates only: `{{ private.piserver.ssh_port }}`. This vars plugin gives every host one variable,
`private`, read once per run from

  1. the file DOTFILES_PRIVATE_FILE (default ~/.config/dotfiles/private.yml), if it exists: outside the repo, mode 600;
     for a machine without Bitwarden, or to prepare the item
  2. else Bitwarden: the notes of the item DOTFILES_PRIVATE_ITEM (default "dotfiles private"), a YAML document, read
     with `bw get notes` from the unlocked vault (BW_SESSION: bootstrap.sh --bitwarden and dot unlock it)

Neither there: `private` is an empty dict, and only what refers to it fails, with a message saying how to unlock.
The structure of the document is in ansible/private.example.yml.
"""

import os
import subprocess

import yaml
from ansible.errors import AnsibleError
from ansible.plugins.vars import BaseVarsPlugin

DOCUMENTATION = """
    name: private
    short_description: personal and secret values from Bitwarden (or a private file outside the repo)
    description: Loads one YAML document, from DOTFILES_PRIVATE_FILE or a Bitwarden item, into the variable `private`.
    options:
      stage:
        default: task
        ini:
          - key: stage
            section: vars_private
        env:
          - name: ANSIBLE_VARS_PLUGIN_STAGE
"""

_CACHE = {}


def load_private():
    if "data" in _CACHE:
        return _CACHE["data"]
    data = {}
    path = os.path.expanduser(os.environ.get("DOTFILES_PRIVATE_FILE", "~/.config/dotfiles/private.yml"))
    item = os.environ.get("DOTFILES_PRIVATE_ITEM", "dotfiles private")
    if os.path.isfile(path):
        with open(path) as fh:
            data = yaml.safe_load(fh) or {}
        source = path
    elif os.environ.get("BW_SESSION"):
        try:
            out = subprocess.run(["bw", "get", "notes", item], capture_output=True, text=True, timeout=120,
                                 env={**os.environ, "BW_NOINTERACTION": "true"})
        except (OSError, subprocess.TimeoutExpired) as e:
            raise AnsibleError("private: could not run the Bitwarden CLI (bw): %s" % e)
        if out.returncode != 0:
            raise AnsibleError("private: Bitwarden has no readable item %r (%s). Create it from "
                               "ansible/private.example.yml (docs/bitwarden.md, 'Private values')"
                               % (item, (out.stderr or out.stdout).strip()[:200]))
        data = yaml.safe_load(out.stdout) or {}
        source = "Bitwarden item %r" % item
    else:
        source = None
    if not isinstance(data, dict):
        raise AnsibleError("private: %s is not a YAML mapping" % source)
    _CACHE["data"] = data
    _CACHE["source"] = source
    return data


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
                        "%s needs the private values (Bitwarden item %r), but Bitwarden is locked and there is no %s. "
                        "Unlock it: export BW_SESSION=$(bw unlock --raw), or run through bootstrap.sh --bitwarden / dot "
                        "with bitwarden on (docs/bitwarden.md, 'Private values')."
                        % (entity.name, os.environ.get("DOTFILES_PRIVATE_ITEM", "dotfiles private"),
                           os.environ.get("DOTFILES_PRIVATE_FILE", "~/.config/dotfiles/private.yml")))
        return {"private": data, "private_source": _CACHE.get("source") or ""}
