#!/usr/bin/env python3
"""mycask: install, upgrade and uninstall macOS apps from Homebrew cask definitions,
without Homebrew.

Cask definitions come from Homebrew's bulk cask index (formulae.brew.sh/api/cask.json),
downloaded at most once a day and reused from a local copy in between. mycask implements the cask artifact, uninstall and zap rules itself, using only
the Python standard library and tools that ship with macOS (curl, hdiutil, ditto, tar,
installer, pkgutil, launchctl, osascript).

Commands:
  install <token>...     install casks (--adopt takes over apps already in place,
                         --force replaces them, --appdir DIR puts the app in another folder;
                         upgrades and uninstalls remember that folder)
  reinstall <token>...   download and install again
  upgrade [<token>...]   upgrade outdated casks, all of them if none given
                         (--greedy also upgrades auto-updating and "latest" casks)
  outdated               list casks with a newer version available
  uninstall <token>...   run the cask's uninstall steps (--zap also removes settings/caches)
  zap <token>...         remove an app's leftover files, even if mycask didn't install it
  list                   installed casks and versions
  pin / unpin <token>... hold a cask at its installed version, or release it
  info <token>           summary of a cask definition
  search <text>          search cask tokens, names and descriptions
  update [--force]       refresh the local indexes (otherwise done at most once a day)
  bundle <file>          install every token in a file (one per line, # for comments;
                         a line may add --appdir=DIR)

Environment:
  MYCASK_TTL        seconds between automatic index refreshes (default 86400 = 1 day)
  MYCASK_API        index URL (default https://formulae.brew.sh/api/cask.json); point it
                    at your own mirror if formulae.brew.sh ever goes away
  MYCASK_PREFIX     where binaries, man pages and completions are linked (default ~/.local)
  MYCASK_ROOT       receipts and staged files (default ~/.local/share/mycask)
  MYCASK_CACHE      download and API cache (default ~/Library/Caches/mycask)
  MYCASK_OVERRIDES  folder of <token>.json files used instead of the API, for pinning or
                    patching definitions (default ~/.config/mycask/casks)
  MYCASK_DEBUG=1    show full Python tracebacks on errors
"""
from __future__ import annotations

import argparse
import copy
import functools
import glob
import hashlib
import json
import os
import platform
import plistlib
import re
import shlex
import shutil
import signal as sigmod
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

HOME = Path.home()
PREFIX = Path(os.environ.get("MYCASK_PREFIX", HOME / ".local")).expanduser()
ROOT = Path(os.environ.get("MYCASK_ROOT", HOME / ".local/share/mycask")).expanduser()
CACHE = Path(os.environ.get("MYCASK_CACHE", HOME / "Library/Caches/mycask")).expanduser()
OVERRIDES = Path(os.environ.get("MYCASK_OVERRIDES", HOME / ".config/mycask/casks")).expanduser()
CASKROOM = ROOT / "Caskroom"
RECEIPTS = ROOT / "receipts"

API_ALL = os.environ.get("MYCASK_API", "https://formulae.brew.sh/api/cask.json")
INDEX_TTL = int(os.environ.get("MYCASK_TTL", 86400))  # seconds between index refreshes
INDEX_FILE = CACHE / "api" / "cask.json"  # keeps the server's Last-Modified time
UA_DEFAULT = "mycask/1.0 (Macintosh; macOS) curl"
UA_FAKE = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
           "(KHTML, like Gecko) Version/18.0 Safari/605.1.15")

# Default destinations, matching Homebrew's defaults.
MOVE_DIRS = {
    "app": Path("/Applications"),
    "suite": Path("/Applications"),
    "colorpicker": HOME / "Library/ColorPickers",
    "prefpane": HOME / "Library/PreferencePanes",
    "qlplugin": HOME / "Library/QuickLook",
    "mdimporter": HOME / "Library/Spotlight",
    "dictionary": HOME / "Library/Dictionaries",
    "font": HOME / "Library/Fonts",
    "service": HOME / "Library/Services",
    "input_method": HOME / "Library/Input Methods",
    "internet_plugin": HOME / "Library/Internet Plug-Ins",
    "keyboard_layout": Path("/Library/Keyboard Layouts"),
    "audio_unit_plugin": HOME / "Library/Audio/Plug-Ins/Components",
    "vst_plugin": HOME / "Library/Audio/Plug-Ins/VST",
    "vst3_plugin": HOME / "Library/Audio/Plug-Ins/VST3",
    "screen_saver": HOME / "Library/Screen Savers",
}
DEFAULT_APPDIR = MOVE_DIRS["app"]  # cask.json targets apps here; --appdir moves them elsewhere
LINK_DIRS = {
    "binary": PREFIX / "bin",
    "command_wrapper": PREFIX / "bin",
    "bash_completion": PREFIX / "share/bash-completion/completions",
    "zsh_completion": PREFIX / "share/zsh/site-functions",
    "fish_completion": PREFIX / "share/fish/vendor_completions.d",
}
INSTALL_ORDER = [
    "preflight_steps", "installer", "app", "suite", "artifact", "colorpicker", "prefpane", "qlplugin",
    "mdimporter", "dictionary", "font", "service", "input_method", "internet_plugin",
    "keyboard_layout", "audio_unit_plugin", "vst_plugin", "vst3_plugin", "screen_saver",
    "pkg", "binary", "command_wrapper", "manpage", "bash_completion", "zsh_completion",
    "fish_completion", "generate_completions_from_executable", "postflight_steps",
]
DIRECTIVE_ORDER = ["early_script", "launchctl", "quit", "signal", "login_item", "kext",
                   "script", "pkgutil", "delete", "trash", "rmdir"]
RUBY_BLOCKS = {"preflight", "postflight", "uninstall_preflight", "uninstall_postflight"}
KNOWN_KINDS = set(INSTALL_ORDER) | {"uninstall", "zap", "stage_only"} | RUBY_BLOCKS
CODENAMES = {27: "golden_gate", 26: "tahoe", 15: "sequoia", 14: "sonoma", 13: "ventura",
             12: "monterey", 11: "big_sur"}
CONTAINER_TYPES = {"dmg": "dmg", "zip": "zip", "pkg": "pkg", "xar": "pkg", "naked": "naked",
                   "tar": "tar", "gzip": "tar", "bzip2": "tar", "xz": "tar", "zstd": "tar",
                   "seven_zip": "7z", "7z": "7z"}

PROTECTED = {Path(p) for p in (
    "/", "/Applications", "/Library", "/System", "/Users", "/usr", "/usr/local", "/usr/local/bin",
    "/opt", "/private", "/var", "/etc", "/bin", "/sbin", "/Library/Application Support",
    "/Library/LaunchAgents", "/Library/LaunchDaemons", "/Library/Extensions",
    "/Library/Preferences", "/Library/PrivilegedHelperTools")}
PROTECTED |= {HOME, HOME / "Library", HOME / "Library/Application Support",
              HOME / "Library/Caches", HOME / "Library/Preferences", HOME / "Library/Containers",
              HOME / "Library/Group Containers", HOME / "Library/LaunchAgents",
              HOME / "Library/Logs", HOME / "Library/Saved Application State",
              HOME / "Desktop", HOME / "Documents", HOME / "Downloads", HOME / ".Trash", HOME / "Applications",
              PREFIX, PREFIX / "bin", PREFIX / "share", CASKROOM, ROOT}
PROTECTED |= set(MOVE_DIRS.values()) | set(LINK_DIRS.values())


class CaskError(Exception):
    pass


LOG_STREAM = sys.stdout


def log(msg):
    print(f"==> {msg}", file=LOG_STREAM, flush=True)


def warn(msg):
    print(f"Warning: {msg}", file=sys.stderr, flush=True)


def run(cmd, sudo=False, check=True, input=None, capture=False):
    cmd = [str(c) for c in cmd]
    if sudo and os.geteuid() != 0:
        cmd = ["sudo"] + cmd
    r = subprocess.run(cmd, input=input,
                       stdout=subprocess.PIPE if capture else None,
                       stderr=subprocess.PIPE if capture else None)
    if check and r.returncode != 0:
        err = (r.stderr or b"").decode(errors="replace").strip() if capture else ""
        raise CaskError(f"command failed ({r.returncode}): {' '.join(cmd)}" + (f"\n{err}" if err else ""))
    return r


# ---------------------------------------------------------------- filesystem helpers

def exists(p):
    p = Path(p)
    return p.exists() or p.is_symlink()


def is_protected(path):
    p = Path(os.path.abspath(str(path)))
    return p in PROTECTED or str(p).startswith("/System/") or len(p.parts) < 3


def remove(path):
    path = Path(path)
    if not exists(path):
        return
    if is_protected(path):
        raise CaskError(f"refusing to remove protected path {path}")
    try:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
    except OSError:
        run(["rm", "-rf", path], sudo=True)


def ensure_dir(d):
    d = Path(d)
    if d.is_dir():
        return
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        run(["mkdir", "-p", d], sudo=True)


def writable_parent(p):
    q = Path(p).parent
    while not q.exists():
        q = q.parent
    return os.access(q, os.W_OK)


def move(src, dest):
    src, dest = Path(src), Path(dest)
    ensure_dir(dest.parent)
    try:
        os.rename(src, dest)
    except OSError:
        need_sudo = not (writable_parent(dest) and writable_parent(src))
        run(["mv", src, dest], sudo=need_sudo)


def symlink(src, dest, force=False):
    src, dest = Path(src), Path(dest)
    ensure_dir(dest.parent)
    if dest.is_symlink() and os.readlink(dest) == str(src):
        return
    if exists(dest):
        if not force:
            raise CaskError(f"{dest} already exists (use --force to overwrite)")
        remove(dest)
    try:
        dest.symlink_to(src)
    except OSError:
        run(["ln", "-s", src, dest], sudo=True)


def expand_text(s):
    # casks name their staged files as $HOMEBREW_PREFIX/Caskroom/<token>/<version>/...; mycask keeps the Caskroom in ROOT
    return (str(s).replace("$HOMEBREW_PREFIX/Caskroom", str(CASKROOM))
            .replace("$HOMEBREW_PREFIX", str(PREFIX))
            .replace("$APPDIR", str(MOVE_DIRS["app"]))
            .replace("$HOME", str(HOME)))


def expand(s, base=None):
    p = Path(os.path.expanduser(expand_text(s)))
    if not p.is_absolute() and base is not None:
        p = Path(base) / p
    return p


def expand_globs(paths):
    out = []
    for s in paths:
        p = expand(s)
        if not p.is_absolute():
            warn(f"skipping relative path {s}")
            continue
        if any(c in str(p) for c in "*?["):
            out += [Path(x) for x in sorted(glob.glob(str(p)))]
        elif exists(p):
            out.append(p)
    return out


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_version(v):
    return re.sub(r"[/:]", "_", str(v))


def caskroom_dir(token, version):
    return CASKROOM / token / safe_version(version)


# ---------------------------------------------------------------- platform

def host_macos():
    v = platform.mac_ver()[0] or "0"
    return tuple(int(x) for x in v.split(".") if x.isdigit())


@functools.lru_cache(maxsize=None)
def host_is_arm():
    r = subprocess.run(["sysctl", "-n", "hw.optional.arm64"], capture_output=True, text=True)
    return r.stdout.strip() == "1"


@functools.lru_cache(maxsize=None)
def platform_key():
    ver = host_macos()
    name = CODENAMES.get(ver[0] if ver else 0)
    if not name:
        return None
    return f"arm64_{name}" if host_is_arm() else name


def apply_variation(meta, key=None):
    key = key or platform_key()
    var = (meta.get("variations") or {}).get(key) if key else None
    meta = {**meta, **var} if var else dict(meta)
    supported = meta.get("supported_platforms")
    if key and supported and key not in supported:
        warn(f"{meta.get('token')} does not list {key} as a supported platform")
    return meta


def parse_version(v):
    v = str(v).lstrip(":")
    by_name = {name: n for n, name in CODENAMES.items()}
    if v in by_name:
        return (by_name[v],)
    try:
        return tuple(int(x) for x in v.split("."))
    except ValueError:
        return None


# ---------------------------------------------------------------- cask definitions

class RemoteIndex:
    """A JSON file downloaded at most once per INDEX_TTL and reused locally in between.

    A conditional request (If-Modified-Since against the server's own timestamp) means an
    unchanged index costs a tiny 304 reply. A bad or suspiciously small download never
    replaces a good copy, and a failed refresh falls back to the cached copy.
    """

    def __init__(self, label, url, path, count):
        self.label, self.url, self.file = label, url, Path(path)
        self.stamp = self.file.with_name(self.file.name + ".checked")
        self.count = count  # returns the number of entries, or raises ValueError
        self.data = None

    def age(self):
        if not self.file.exists():
            return None
        ref = self.stamp if self.stamp.exists() else self.file
        return time.time() - ref.stat().st_mtime

    def _checked(self):
        self.stamp.touch()
        os.utime(self.stamp)

    def refresh(self, force=False):
        age = self.age()
        if age is not None and age < INDEX_TTL and not force:
            return False
        ensure_dir(self.file.parent)
        part = self.file.with_name(self.file.name + ".part")
        if exists(part):
            part.unlink()
        log(f"Updating the {self.label}")
        cmd = ["curl", "-sSL", "--fail", "--retry", "3", "--compressed", "-R", "-A", UA_DEFAULT,
               "-o", part, "-w", "%{http_code}"]
        if self.file.exists():
            cmd += ["-z", self.file]
        r = run(cmd + [self.url], check=False, capture=True)
        code = r.stdout.decode(errors="replace").strip()[-3:]
        if r.returncode != 0:
            if exists(part):
                part.unlink()
            raise CaskError(f"{self.label} download failed (curl exit {r.returncode}, HTTP {code or '?'})")
        if code == "304" or not part.exists() or part.stat().st_size == 0:
            if exists(part):
                part.unlink()
            self._checked()
            log(f"The {self.label} is already up to date")
            return False
        try:
            new_count = self.count(json.loads(part.read_bytes()))
        except ValueError as e:
            part.unlink()
            raise CaskError(f"downloaded {self.label} is not valid: {e}")
        if self.file.exists():
            try:
                old_count = self.count(json.loads(self.file.read_bytes()))
            except ValueError:
                old_count = 0
            if old_count and new_count < old_count * 0.5:
                part.unlink()
                self._checked()
                raise CaskError(f"new {self.label} has {new_count} entries against {old_count} before; keeping the old one")
        os.replace(part, self.file)
        self._checked()
        log(f"The {self.label} was updated ({new_count} entries)")
        return True

    def load(self, offline=False, force=False):
        if self.data is not None and not force:
            return self.data
        if not offline:
            try:
                self.refresh(force=force)
            except CaskError as e:
                if not self.file.exists():
                    raise
                warn(f"{e}; using the cached copy from {self.age() / 3600:.0f} hours ago")
        if not self.file.exists():
            raise CaskError(f"no {self.label} yet; run `mycask update` while online")
        self.data = json.loads(self.file.read_bytes())
        return self.data


def _count_list(key):
    def count(data):
        if not isinstance(data, list) or not data or key not in data[0]:
            raise ValueError("unexpected format")
        return len(data)
    return count


CASK_INDEX = RemoteIndex("cask index", API_ALL, INDEX_FILE, _count_list("token"))
_INDEX = None


def index_age():
    return CASK_INDEX.age()


def load_index(offline=False, force=False):
    """Return (casks by token, old token -> current token), refreshing once a day."""
    global _INDEX
    if _INDEX is not None and not force:
        return _INDEX
    casks = CASK_INDEX.load(offline, force)
    by_token = {c["token"]: c for c in casks}
    aliases = {}
    for c in casks:
        for old in c.get("old_tokens") or []:
            aliases.setdefault(old, c["token"])
    _INDEX = (by_token, aliases)
    return _INDEX


def resolve_token(token, offline=False):
    if (OVERRIDES / f"{token}.json").exists():
        return token
    by_token, aliases = load_index(offline)
    if token in by_token:
        return token
    if token in aliases:
        log(f"'{token}' is now called '{aliases[token]}'")
        return aliases[token]
    raise CaskError(f"no cask named '{token}'")


def fetch_meta(token, offline=False):
    if "/" in token:
        raise CaskError(f"'{token}': only casks from the main Homebrew cask repo are supported")
    override = OVERRIDES / f"{token}.json"
    if override.exists():
        return apply_variation(json.loads(override.read_text()))
    by_token, _ = load_index(offline)
    real = resolve_token(token, offline)
    return apply_variation(copy.deepcopy(by_token[real]))


def artifact_entries(meta):
    """Yield (kind, args, target) for each artifact stanza.

    The API puts a resolved destination in a sibling "target" key, e.g.
    {"app": ["Firefox.app"], "target": "/Applications/Firefox.app"}.
    """
    for art in meta.get("artifacts") or []:
        target = art.get("target")
        for kind, args in art.items():
            if kind != "target":
                yield kind, args, target


def split_args(args):
    if not isinstance(args, list):
        args = [args]
    src = next((a for a in args if isinstance(a, str)), None)
    opts = {}
    for a in args:
        if isinstance(a, dict):
            opts.update(a)
    return src, opts


def directives(meta, which):
    merged = {}
    for kind, args, _ in artifact_entries(meta):
        if kind != which:
            continue
        for a in (args if isinstance(args, list) else [args]):
            if not isinstance(a, dict):
                continue
            for k, v in a.items():
                if v is None:
                    continue
                bucket = merged.setdefault(k, [])
                if k == "signal":
                    bucket.extend(v if v and isinstance(v[0], list) else [v])
                elif isinstance(v, list):
                    bucket.extend(v)
                else:
                    bucket.append(v)
    return merged


def check_requirements(meta, installed):
    token = meta["token"]
    if meta.get("disabled"):
        raise CaskError(f"{token} is disabled upstream: {meta.get('disable_reason') or 'no reason given'}")
    if meta.get("deprecated"):
        warn(f"{token} is deprecated: {meta.get('deprecation_reason') or 'no reason given'}")
    dep = meta.get("depends_on") or {}
    host = host_macos()
    for op, vals in (dep.get("macos") or {}).items():
        wants = [w for w in (parse_version(v) for v in (vals if isinstance(vals, list) else [vals])) if w]
        if not wants:
            continue
        h = lambda w: host[:len(w)]
        ok = {">=": lambda: h(wants[0]) >= wants[0], "<=": lambda: h(wants[0]) <= wants[0],
              ">": lambda: h(wants[0]) > wants[0], "<": lambda: h(wants[0]) < wants[0],
              "==": lambda: any(h(w) == w for w in wants)}.get(op)
        if ok and not ok():
            raise CaskError(f"{token} requires macOS {op} {', '.join(map(str, vals if isinstance(vals, list) else [vals]))}")
    archs = dep.get("arch") or []
    if archs:
        norm = {"arm64": "arm", "x86_64": "intel"}
        types = set()
        for a in archs:
            t = a.get("type") if isinstance(a, dict) else str(a).lstrip(":")
            types.add(norm.get(t, t))
        host_type = "arm" if host_is_arm() else "intel"
        if host_type not in types:
            raise CaskError(f"{token} requires a {'/'.join(sorted(types))} Mac")
    if dep.get("formula"):
        warn(f"{token} also needs these command-line tools: {', '.join(dep['formula'])} "
             "(install them with MacPorts or mise)")
    for other in (meta.get("conflicts_with") or {}).get("cask") or []:
        if other in installed:
            warn(f"{token} conflicts with installed cask {other}")


def show_caveats(meta):
    c = meta.get("caveats")
    if c:
        print("==> Caveats\n" + expand_text(c).rstrip())


# ---------------------------------------------------------------- download and staging

def download(meta):
    url = meta.get("url")
    if not url:
        raise CaskError(f"{meta['token']} has no download URL for this Mac")
    specs = meta.get("url_specs") or {}
    name = unquote(Path(urlparse(url).path).name) or "download"
    version = str(meta["version"])
    dest = CACHE / "downloads" / f"{meta['token']}--{safe_version(version)}--{name}"
    expected = meta.get("sha256")
    verify = bool(expected) and str(expected).lstrip(":") != "no_check"
    if exists(dest) and version != "latest" and verify and file_sha256(dest) == expected:
        log(f"Using cached download {dest.name}")
        return dest, name
    ensure_dir(dest.parent)

    cmd = ["curl", "-fL", "-#", "--retry", "3", "--connect-timeout", "30"]
    ua = str(specs.get("user_agent") or "").lstrip(":")
    cmd += ["-A", UA_FAKE if ua == "fake" else (UA_DEFAULT if ua in ("", "default") else ua)]
    if specs.get("referer"):
        cmd += ["-e", specs["referer"]]
    headers = specs.get("header") or specs.get("headers") or []
    for h in ([headers] if isinstance(headers, str) else headers):
        cmd += ["-H", h]
    if specs.get("cookies"):
        cmd += ["-b", "; ".join(f"{k}={v}" for k, v in specs["cookies"].items())]
    using = str(specs.get("using") or "").lstrip(":")
    if specs.get("data"):
        for k, v in specs["data"].items():
            cmd += ["--data-urlencode", f"{k}={v}"]
    elif using == "post":
        cmd += ["-X", "POST"]
    if using and using not in ("post", "curl", "homebrew_curl"):
        raise CaskError(f"download strategy '{using}' is not supported")

    part = Path(f"{dest}.part")
    log(f"Downloading {url}")
    run(cmd + ["-o", part, url])
    if verify:
        actual = file_sha256(part)
        if actual != expected:
            part.unlink()
            raise CaskError(f"SHA-256 mismatch for {meta['token']}\n  expected {expected}\n  actual   {actual}")
    else:
        warn(f"{meta['token']} has no checksum; the download can't be verified")
    os.replace(part, dest)
    return dest, name


def sniff(f):
    f = Path(f)
    with open(f, "rb") as fh:
        head = fh.read(512)
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        tail = b""
        if size >= 512:
            fh.seek(size - 512)
            tail = fh.read(4)
    if tail == b"koly":
        return "dmg"
    if head[:4] in (b"PK\x03\x04", b"PK\x05\x06"):
        return "zip"
    if head[:4] == b"xar!":
        return "pkg"
    if (head[:2] == b"\x1f\x8b" or head[:3] == b"BZh" or head[:6] == b"\xfd7zXZ\x00"
            or head[:4] == b"\x28\xb5\x2f\xfd" or head[257:262] == b"ustar"):
        return "tar"
    if head[:6] == b"7z\xbc\xaf\x27\x1c":
        return "7z"
    if f.suffix.lower() == ".dmg":
        return "dmg"
    return "naked"


def stage_dmg(f, dest):
    mnt_root = tempfile.mkdtemp(prefix="mycask-mnt-")
    out = run(["hdiutil", "attach", "-plist", "-nobrowse", "-readonly", "-noautoopen",
               "-mountrandom", mnt_root, f], input=b"qy\n", capture=True).stdout
    start = out.find(b"<?xml")
    entities = plistlib.loads(out[start:]).get("system-entities", []) if start >= 0 else []
    mounts = [e["mount-point"] for e in entities if "mount-point" in e]
    skip = {".Trashes", ".fseventsd", ".Spotlight-V100", ".DS_Store", ".TemporaryItems",
            ".DocumentRevisions-V100"}
    try:
        for m in mounts:
            for entry in Path(m).iterdir():
                if entry.name in skip:
                    continue
                target = Path(dest) / entry.name
                if entry.is_symlink():
                    os.symlink(os.readlink(entry), target)
                else:
                    run(["ditto", entry, target])
    finally:
        for m in mounts:
            run(["hdiutil", "detach", m, "-force", "-quiet"], check=False)
        shutil.rmtree(mnt_root, ignore_errors=True)


def extract(f, kind, dest, name):
    if kind == "dmg":
        stage_dmg(f, dest)
    elif kind == "zip":
        run(["ditto", "-x", "-k", f, dest])
    elif kind == "tar":
        run(["tar", "-xf", f, "-C", dest])
    elif kind == "7z":
        exe = shutil.which("7zz") or shutil.which("7z")
        if exe:
            run([exe, "x", "-y", f"-o{dest}", f], capture=True)
        else:
            run(["tar", "-xf", f, "-C", dest])
    else:
        shutil.copy2(f, Path(dest) / name)


def is_git(meta):
    """A cask whose URL is a git repository (url "...git", branch:/only_path:, e.g. font-source-code-pro)."""
    using = str((meta.get("url_specs") or {}).get("using") or "").lstrip(":")
    return str(meta.get("url") or "").endswith(".git") or using == "git"


def stage_git(meta, staged):
    """Homebrew's git strategy: a shallow clone (only `only_path` of it, when the cask names one) whose files become
    the staged files."""
    if not shutil.which("git"):
        raise CaskError(f"{meta['token']} comes from a git repository and needs git (Command Line Tools)")
    specs = meta.get("url_specs") or {}
    only = str(specs.get("only_path") or "").strip("/")
    ensure_dir(CACHE)
    tmp = Path(tempfile.mkdtemp(prefix="git-", dir=CACHE))
    repo = tmp / "repo"
    try:
        log(f"Cloning {meta['url']}" + (f" ({only})" if only else ""))
        cmd = ["git", "clone", "--quiet", "--depth", "1", "--filter=blob:none"] + (["--sparse"] if only else [])
        ref = specs.get("branch") or specs.get("tag")
        if ref:
            cmd += ["--branch", str(ref)]
        run(cmd + [meta["url"], repo])
        if specs.get("revision"):
            run(["git", "-C", repo, "fetch", "--quiet", "--depth", "1", "origin", str(specs["revision"])])
            run(["git", "-C", repo, "checkout", "--quiet", "FETCH_HEAD"])
        if only:
            run(["git", "-C", repo, "sparse-checkout", "set", only])
        src = repo / only if only else repo
        if not src.is_dir():
            raise CaskError(f"{only or meta['url']} not found in the repository")
        shutil.copytree(src, staged, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def stage(meta, staged):
    if exists(staged):
        remove(staged)
    staged.mkdir(parents=True)
    if is_git(meta):
        stage_git(meta, staged)
        (staged / ".mycask-container").write_text("git")
        return staged
    f, name = download(meta)
    container = meta.get("container") or {}
    ctype = str(container.get("type") or "").lstrip(":")
    kind = CONTAINER_TYPES.get(ctype) if ctype else None
    if ctype and not kind:
        warn(f"container type '{ctype}' not recognised; detecting it automatically")
    kind = kind or sniff(f)
    log(f"Extracting {kind} download")
    extract(f, kind, staged, name)
    (staged / ".mycask-container").write_text(kind)
    nested = container.get("nested")
    if nested:
        nf = staged / nested
        if not exists(nf):
            hits = list(staged.rglob(Path(nested).name))
            if not hits:
                raise CaskError(f"nested container {nested} not found")
            nf = hits[0]
        extract(nf, sniff(nf), staged, nf.name)
        remove(nf)
    return staged


def find_source(staged, rel, single_suffix=None):
    if rel is None:
        raise CaskError("artifact has no source path")
    p = expand(rel, staged)
    if exists(p):
        return p
    name = Path(rel).name
    name = glob.escape(name)   # a file name can hold glob characters: SourceCodePro-Italic[wght].ttf
    for pattern in (name, f"*/{name}", f"*/*/{name}"):
        hits = list(staged.glob(pattern))
        if len(hits) == 1:
            return hits[0]
    marker = staged / ".mycask-container"
    naked = marker.exists() and marker.read_text() in ("naked", "pkg")
    if single_suffix is not None and (naked or single_suffix):
        top = [c for c in staged.iterdir() if not c.name.startswith(".")]
        cands = [c for c in top if single_suffix == "" or c.name.endswith(single_suffix)]
        if len(cands) == 1:
            return cands[0]
    raise CaskError(f"'{rel}' not found in the download")


# ---------------------------------------------------------------- install artifacts

def add_quarantine(path):
    value = f"0081;{int(time.time()):x};mycask;"
    run(["xattr", "-w", "com.apple.quarantine", value, path], check=False, capture=True)


def do_move(kind, src, target, staged, opts, items):
    srcp = find_source(staged, src)
    if target:
        dest = expand(target, MOVE_DIRS.get(kind))
    elif kind == "artifact":
        raise CaskError("'artifact' stanza has no target")
    else:
        dest = MOVE_DIRS[kind] / srcp.name
    if kind in ("app", "suite") and MOVE_DIRS[kind] != DEFAULT_APPDIR:
        try:  # cask.json gives absolute /Applications/... targets
            dest = MOVE_DIRS[kind] / dest.relative_to(DEFAULT_APPDIR)
        except ValueError:
            pass
    if exists(dest):
        if opts.adopt:
            log(f"Adopting existing {dest}")
            remove(srcp)
            items.append({"kind": kind, "path": str(dest), "mode": "move", "adopted": True})
            return
        if not opts.force:
            raise CaskError(f"{dest} already exists; use --adopt to take it over or --force to replace it")
        remove(dest)
    log(f"Moving {kind.replace('_', ' ')} '{srcp.name}' to '{dest}'")
    move(srcp, dest)
    items.append({"kind": kind, "path": str(dest), "mode": "move"})
    if opts.quarantine and kind in ("app", "suite"):
        add_quarantine(dest)


def do_link(kind, src, target, staged, opts, items):
    srcp = find_source(staged, src, single_suffix="" if kind == "binary" else None)
    if kind == "manpage":
        m = re.search(r"\.([1-8])(?:\.gz)?$", srcp.name)
        if not m:
            raise CaskError(f"can't tell the man section of {srcp.name}")
        default = PREFIX / "share/man" / f"man{m.group(1)}" / srcp.name
    else:
        default = LINK_DIRS[kind] / srcp.name
    dest = expand(target, default.parent) if target else default
    if kind == "binary" and srcp.is_file() and not os.access(srcp, os.X_OK):
        try:
            srcp.chmod(srcp.stat().st_mode | 0o111)
        except OSError:
            run(["chmod", "+x", srcp], sudo=True, check=False)
    log(f"Linking {kind.replace('_', ' ')} '{srcp.name}' to '{dest}'")
    if opts.adopt and dest.is_symlink():
        remove(dest)
    symlink(srcp, dest, opts.force)
    items.append({"kind": kind, "path": str(dest), "mode": "link", "source": str(srcp)})


def do_wrapper(name, o, target, staged, opts, items):
    exe = o.get("executable")
    if not name or not exe:
        raise CaskError("command_wrapper needs a name and an executable")
    wrapper_dir = staged / ".homebrew-command-wrappers"
    wrapper_dir.mkdir(exist_ok=True)
    wrapper = wrapper_dir / name
    wrapper.write_text(f'#!/bin/bash\nexec {shlex.quote(str(expand(exe, staged)))} "$@"\n')
    wrapper.chmod(0o755)
    dest = expand(target, LINK_DIRS["command_wrapper"]) if target else LINK_DIRS["command_wrapper"] / name
    log(f"Linking command wrapper '{name}' to '{dest}'")
    if opts.adopt and dest.is_symlink():
        remove(dest)
    symlink(wrapper, dest, opts.force)
    items.append({"kind": "command_wrapper", "path": str(dest), "mode": "link", "source": str(wrapper)})


def do_pkg(src, o, staged):
    pkg = find_source(staged, src, single_suffix=".pkg")
    cmd = ["installer", "-pkg", pkg, "-target", "/"]
    if o.get("choices"):
        xml = staged / ".mycask-choices.xml"
        xml.write_bytes(plistlib.dumps(o["choices"]))
        cmd += ["-applyChoiceChangesXML", xml]
    if o.get("allow_untrusted"):
        cmd.append("-allowUntrusted")
    log(f"Running the installer for {pkg.name} (needs your password)")
    run(cmd, sudo=True)


def do_installer(o, staged):
    if "manual" in o:
        path = find_source(staged, o["manual"])
        log(f"This cask needs a manual step: opening {path}. Finish the installer, then carry on.")
        run(["open", path], check=False)
    elif "script" in o:
        s = o["script"]
        if isinstance(s, str):
            d = dict(o)
            d.pop("script")
            d["executable"] = s
            s = d
        h_script([s], staged)


def step_path(s, staged):
    names = {"appdir": str(MOVE_DIRS["app"]), "homebrew_prefix": str(PREFIX), "home": str(HOME),
             "staged_path": str(staged)}

    def sub(m):
        key = m.group(1).strip()
        if key not in names:
            raise CaskError(f"unknown placeholder {{{{{key}}}}} in cask steps")
        return names[key]

    return expand(re.sub(r"\{\{\s*(\w+)\s*\}\}", sub, str(s)))


def resolve_step_path(spec, staged):
    if isinstance(spec, dict):
        base, rel = spec.get("base"), spec.get("path", "")
        if base:
            bases = {"home": HOME, "appdir": MOVE_DIRS["app"], "homebrew_prefix": PREFIX,
                     "staged_path": staged}
            if bases.get(base) is None:
                raise CaskError(f"unknown path base '{base}' in cask steps")
            return Path(bases[base]) / rel
        return step_path(rel, staged)
    return step_path(spec, staged)


def guards_ok(guards, staged):
    for g in guards or []:
        p, cond = resolve_step_path(g.get("path", ""), staged), g.get("condition")
        if cond == "unless_exists" and exists(p):
            return False
        if cond == "if_exists" and not exists(p):
            return False
        if cond not in ("unless_exists", "if_exists"):
            warn(f"unknown step guard '{cond}'; skipping that step")
            return False
    return True


def do_steps(args, staged, opts, items):
    """Declarative pre/postflight steps, e.g. Docker Desktop's kubectl symlink."""
    for block in (args if isinstance(args, list) else [args]):
        for step in (block.get("steps") or []) if isinstance(block, dict) else []:
            kind = step.get("type")
            if not guards_ok(step.get("guards"), staged):
                continue
            if kind == "mkdir_p":
                ensure_dir(resolve_step_path(step.get("path"), staged))
                continue
            if kind != "symlink":
                warn(f"unsupported cask step type '{kind}' skipped")
                continue
            src = resolve_step_path(step["source"], staged)
            dest = resolve_step_path(step["target"], staged)
            log(f"Linking '{src.name}' to '{dest}'")
            symlink(src, dest, force=bool(step.get("force")) or opts.force)
            if step.get("uninstall"):
                items.append({"kind": "step_symlink", "path": str(dest), "mode": "link", "source": str(src)})


COMPLETION_FILES = {"bash": ("bash_completion", "{}"), "zsh": ("zsh_completion", "_{}"),
                    "fish": ("fish_completion", "{}.fish")}


def do_gen_completions(args, staged, opts, items):
    words = [a for a in args if isinstance(a, str)]
    o = {}
    for a in args:
        if isinstance(a, dict):
            o.update(a)
    exe = find_source(staged, words[0])
    extra = words[1:]
    base = o.get("base_name") or Path(words[0]).name
    fmt = str(o.get("shell_parameter_format") or "").lstrip(":")
    for shell in o.get("shells") or ["bash", "zsh", "fish"]:
        env = dict(os.environ)
        if fmt == "":
            argv = extra + [shell]
        elif fmt == "flag":
            argv = extra + [f"--{shell}"]
        elif fmt == "arg":
            argv = extra + [f"--shell={shell}"]
        elif fmt == "none":
            argv = extra
        elif fmt == "cobra":
            argv = extra + ["completion", shell]
        elif fmt == "clap":
            argv, env["COMPLETE"] = extra, shell
        elif fmt == "click":
            argv = extra
            env[f"_{base.upper().replace('-', '_')}_COMPLETE"] = f"{shell}_source"
        else:
            warn(f"completion format '{fmt}' not supported; skipping {base} completions")
            return
        if shell not in COMPLETION_FILES:
            continue
        r = subprocess.run([str(exe)] + argv, capture_output=True, env=env)
        if r.returncode != 0 or not r.stdout:
            warn(f"could not generate {shell} completions for {base}")
            continue
        kind, pattern = COMPLETION_FILES[shell]
        dest = LINK_DIRS[kind] / pattern.format(base)
        if exists(dest) and not opts.force:
            warn(f"{dest} already exists; not overwriting")
            continue
        ensure_dir(dest.parent)
        log(f"Generating {shell} completion '{dest}'")
        try:
            dest.write_bytes(r.stdout)
        except OSError:
            run(["tee", dest], sudo=True, input=r.stdout, capture=True)
        items.append({"kind": "completion", "path": str(dest), "mode": "file"})


def bundle_archs(exe):
    r = run(["lipo", "-archs", exe], check=False, capture=True)
    return set(r.stdout.decode().split()) if r.returncode == 0 else set()


def check_bundle_compat(meta, staged, opts):
    """Read each app's own Info.plist and binary: the vendor's word beats the cask's."""
    if getattr(opts, "skip_compat", False):
        return
    host_arch = "arm64" if host_is_arm() else "x86_64"
    for kind, args, _ in artifact_entries(meta):
        if kind not in ("app", "suite"):
            continue
        src, _ = split_args(args)
        try:
            app = find_source(staged, src)
        except CaskError:
            continue
        info_file = app / "Contents/Info.plist"
        if not info_file.exists():
            continue
        info = plistlib.loads(info_file.read_bytes())
        by_arch = info.get("LSMinimumSystemVersionByArchitecture") or {}
        minimum = by_arch.get(host_arch) or info.get("LSMinimumSystemVersion")
        want = parse_version(minimum) if minimum else None
        if want and host_macos()[:len(want)] < want:
            raise CaskError(f"{app.name} {meta['version']} needs macOS {minimum} or later")
        exe = app / "Contents/MacOS" / str(info.get("CFBundleExecutable", ""))
        archs = bundle_archs(exe) if exe.is_file() else set()
        if archs and host_arch not in archs:
            if host_arch == "arm64" and "x86_64" in archs:
                warn(f"{app.name} is Intel-only and will run under Rosetta")
            else:
                raise CaskError(f"{app.name} {meta['version']} has no {host_arch} code ({', '.join(sorted(archs))} only)")


def install_artifacts(meta, staged, opts, items):
    entries = list(artifact_entries(meta))
    for kind, _, _ in entries:
        if kind in ("preflight", "postflight"):
            warn(f"{meta['token']} has a Ruby {kind} block, which the JSON API doesn't include; "
                 f"if the app misbehaves, read {meta.get('ruby_source_path', 'the cask source')}")
        elif kind not in KNOWN_KINDS:
            warn(f"unsupported artifact type '{kind}' in {meta['token']} skipped")
    for want in INSTALL_ORDER:
        for kind, args, target in entries:
            if kind != want:
                continue
            src, o = split_args(args)
            target = o.get("target") or target
            if kind in ("preflight_steps", "postflight_steps"):
                do_steps(args, staged, opts, items)
            elif kind == "generate_completions_from_executable":
                do_gen_completions(args if isinstance(args, list) else [args], staged, opts, items)
            elif kind == "installer":
                do_installer(o, staged)
            elif kind == "pkg":
                do_pkg(src, o, staged)
            elif kind in MOVE_DIRS or kind == "artifact":
                do_move(kind, src, target, staged, opts, items)
            elif kind == "command_wrapper":
                do_wrapper(src, o, target, staged, opts, items)
            else:
                do_link(kind, src, target, staged, opts, items)


def rollback(items):
    for it in reversed(items):
        if it.get("adopted"):
            continue
        try:
            remove(Path(it["path"]))
        except CaskError as e:
            warn(str(e))


# ---------------------------------------------------------------- uninstall directives

def bundle_pids(bid):
    out = run(["launchctl", "list"], check=False, capture=True).stdout.decode(errors="replace")
    pat = re.compile(r"^application\." + re.escape(bid) + r"\.\d+")
    pids = []
    for line in out.splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) == 3 and parts[0].isdigit() and pat.match(parts[2]):
            pids.append(int(parts[0]))
    return pids


def h_quit(ids, staged):
    for bid in ids:
        if not bundle_pids(bid):
            continue
        log(f"Quitting {bid}")
        run(["osascript", "-e", f'tell application id "{bid}" to quit'], check=False, capture=True)
        for _ in range(20):
            if not bundle_pids(bid):
                break
            time.sleep(0.5)
        else:
            warn(f"{bid} did not quit")


def h_signal(pairs, staged):
    for pair in pairs:
        sig, bid = pair[0], pair[1]
        signum = getattr(sigmod, "SIG" + str(sig).upper().replace("SIG", "", 1), None)
        if signum is None:
            warn(f"unknown signal {sig}")
            continue
        for pid in bundle_pids(bid):
            log(f"Sending SIG{str(sig).upper()} to {bid} (pid {pid})")
            try:
                os.kill(pid, signum)
            except PermissionError:
                run(["kill", f"-{int(signum)}", pid], sudo=True, check=False)
            except ProcessLookupError:
                pass


def h_login_item(names, staged):
    for n in names:
        log(f"Removing login item {n}")
        run(["osascript", "-e",
             f'tell application "System Events" to delete every login item whose name is "{n}"'],
            check=False, capture=True)


def h_launchctl(labels, staged):
    uid = os.getuid()
    for label in labels:
        run(["launchctl", "bootout", f"gui/{uid}/{label}"], check=False, capture=True)
        sys_plists = [Path(d) / f"{label}.plist" for d in ("/Library/LaunchDaemons", "/Library/LaunchAgents")]
        loaded = run(["launchctl", "print", f"system/{label}"], check=False, capture=True).returncode == 0
        if loaded or any(p.exists() for p in sys_plists):
            log(f"Removing launchctl service {label}")
            run(["launchctl", "bootout", f"system/{label}"], sudo=True, check=False, capture=True)
        for p in sys_plists + [HOME / "Library/LaunchAgents" / f"{label}.plist"]:
            if exists(p):
                remove(p)


def h_kext(ids, staged):
    for bid in ids:
        log(f"Unloading kernel extension {bid}")
        run(["kmutil", "unload", "-b", bid], sudo=True, check=False, capture=True)
        out = run(["kextfind", "-b", bid], check=False, capture=True).stdout.decode(errors="replace")
        for line in out.splitlines():
            p = Path(line.strip())
            if p.suffix == ".kext" and p.exists():
                remove(p)


def h_script(scripts, staged):
    for s in scripts:
        if isinstance(s, str):
            s = {"executable": s}
        raw = s["executable"]
        exe = expand(raw, staged)
        if not exists(exe) and shutil.which(raw):
            exe = Path(shutil.which(raw))
        if not exists(exe):
            raise CaskError(f"script {raw} not found")
        if not os.access(exe, os.X_OK):
            try:
                exe.chmod(exe.stat().st_mode | 0o111)
            except OSError:
                pass
        args = [expand_text(a) for a in s.get("args") or []]
        inp = s.get("input")
        if isinstance(inp, list):
            inp = "\n".join(inp) + "\n"
        log(f"Running {exe.name}")
        r = run([exe] + args, sudo=bool(s.get("sudo")), check=False,
                capture=not s.get("print_stdout"), input=inp.encode() if inp else None)
        if r.returncode != 0 and s.get("must_succeed", True):
            raise CaskError(f"{exe} exited with status {r.returncode}")


def h_pkgutil(patterns, staged):
    for pat in patterns:
        out = run(["pkgutil", f"--pkgs={pat}"], check=False, capture=True).stdout.decode()
        for pid in out.split():
            log(f"Removing files installed by package {pid}")
            info = plistlib.loads(run(["pkgutil", "--pkg-info-plist", pid], capture=True).stdout)
            root = Path(info.get("volume") or "/") / (info.get("install-location") or "")
            files = run(["pkgutil", "--only-files", "--files", pid], capture=True).stdout.decode().splitlines()
            dirs = run(["pkgutil", "--only-dirs", "--files", pid], capture=True).stdout.decode().splitlines()
            dpaths = sorted({root / d for d in dirs if d}, key=lambda p: len(p.parts), reverse=True)
            targets = [root / f for f in files if f] + [d / ".DS_Store" for d in dpaths]
            targets = [t for t in targets if not str(t).startswith("/System/")]
            if targets:
                run(["xargs", "-0", "rm", "-f"], sudo=True, check=False, capture=True,
                    input=b"\0".join(str(t).encode() for t in targets))
            empties = [d for d in dpaths if not is_protected(d)]
            if empties:
                run(["xargs", "-0", "rmdir"], sudo=True, check=False, capture=True,
                    input=b"\0".join(str(d).encode() for d in empties))
            run(["pkgutil", "--forget", pid], sudo=True, check=False, capture=True)


def h_delete(paths, staged):
    for p in expand_globs(paths):
        try:
            log(f"Removing {p}")
            remove(p)
        except CaskError as e:
            warn(str(e))


def h_trash(paths, staged):
    trash = HOME / ".Trash"
    for p in expand_globs(paths):
        if is_protected(p):
            warn(f"refusing to trash protected path {p}")
            continue
        log(f"Trashing {p}")
        dest, n = trash / p.name, 1
        while exists(dest):
            dest = trash / f"{p.stem} {n}{p.suffix}"
            n += 1
        try:
            os.rename(p, dest)
            continue
        except OSError:
            pass
        quoted = str(p).replace("\\", "\\\\").replace('"', '\\"')
        r = run(["osascript", "-e", f'tell application "Finder" to delete (POSIX file "{quoted}" as alias)'],
                check=False, capture=True)
        if r.returncode != 0:
            warn(f"could not trash {p}")


def h_rmdir(paths, staged):
    for p in expand_globs(paths):
        if not p.is_dir() or p.is_symlink() or is_protected(p):
            continue
        try:
            children = list(p.iterdir())
        except OSError:
            continue
        if children and all(c.name == ".DS_Store" for c in children):
            remove(p / ".DS_Store")
            children = []
        if children:
            continue
        try:
            p.rmdir()
        except OSError:
            run(["rmdir", p], sudo=True, check=False, capture=True)


HANDLERS = {"early_script": h_script, "launchctl": h_launchctl, "quit": h_quit,
            "signal": h_signal, "login_item": h_login_item, "kext": h_kext, "script": h_script,
            "pkgutil": h_pkgutil, "delete": h_delete, "trash": h_trash, "rmdir": h_rmdir}


def run_directives(d, staged, only=None):
    for key in DIRECTIVE_ORDER:
        if only and key not in only:
            continue
        if d.get(key):
            try:
                HANDLERS[key](d[key], staged)
            except CaskError as e:
                warn(f"{key}: {e}")
    if not only:
        for key in sorted(set(d) - set(DIRECTIVE_ORDER)):
            warn(f"unsupported directive '{key}' ignored")


# ---------------------------------------------------------------- receipts

def receipt_file(token):
    return RECEIPTS / f"{token}.json"


def load_receipt(token):
    f = receipt_file(token)
    return json.loads(f.read_text()) if f.exists() else None


def save_receipt(meta, staged, items, keep=None):
    RECEIPTS.mkdir(parents=True, exist_ok=True)
    slim = {k: v for k, v in meta.items() if k not in ("analytics", "language_variations", "languages")}
    rec = {"token": meta["token"], "version": str(meta["version"]), "installed_at": int(time.time()),
           "staged": str(staged), "items": items, "meta": slim}
    for k in ("pinned",):
        if keep and keep.get(k):
            rec[k] = keep[k]
    if MOVE_DIRS["app"] != DEFAULT_APPDIR:
        rec["appdir"] = str(MOVE_DIRS["app"])
    f = receipt_file(meta["token"])
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(rec, indent=1))
    os.replace(tmp, f)


def update_receipt(token, **fields):
    rec = load_receipt(token)
    rec.update(fields)
    for k, v in fields.items():
        if v is None:
            rec.pop(k, None)
    f = receipt_file(token)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(rec, indent=1))
    os.replace(tmp, f)


def installed_tokens():
    return sorted(p.stem for p in RECEIPTS.glob("*.json")) if RECEIPTS.exists() else []


def with_appdir(fn):
    """Run a cask operation with the app folder it asked for (--appdir), else the one its receipt remembers."""
    @functools.wraps(fn)
    def wrapper(token, opts, *args, **kwargs):
        chosen = getattr(opts, "appdir", None) or (load_receipt(token) or {}).get("appdir")
        saved = MOVE_DIRS["app"], MOVE_DIRS["suite"]
        if chosen:
            MOVE_DIRS["app"] = MOVE_DIRS["suite"] = Path(chosen).expanduser().absolute()
        try:
            return fn(token, opts, *args, **kwargs)
        finally:
            MOVE_DIRS["app"], MOVE_DIRS["suite"] = saved
    return wrapper


# ---------------------------------------------------------------- operations

@with_appdir
def install(token, opts, seen):
    token = resolve_token(token, opts.offline)
    if token in seen:
        return
    seen.add(token)
    if load_receipt(token):
        log(f"{token} is already installed (use reinstall or upgrade)")
        return
    meta = fetch_meta(token, opts.offline)
    check_requirements(meta, installed_tokens())
    for dep in (meta.get("depends_on") or {}).get("cask") or []:
        install(dep, opts, seen)
    log(f"Installing {token} {meta['version']}")
    staged = stage(meta, caskroom_dir(token, meta["version"]))
    items = []
    try:
        check_bundle_compat(meta, staged, opts)
        install_artifacts(meta, staged, opts, items)
    except BaseException:
        rollback(items)
        remove(staged)
        try:
            staged.parent.rmdir()
        except OSError:
            pass
        raise
    save_receipt(meta, staged, items)
    show_caveats(meta)
    log(f"{token} {meta['version']} installed")


@with_appdir
def upgrade(token, opts, force=False):
    rec = load_receipt(token)
    if not rec:
        raise CaskError(f"{token} is not installed")
    try:
        meta = fetch_meta(token, opts.offline)
    except CaskError as e:
        if "no cask named" in str(e):
            return "gone"
        raise
    meta = {**meta, "token": token}
    old_v, new_v = rec["version"], str(meta["version"])
    if not force:
        if new_v == old_v and new_v != "latest":
            return "current"
        if rec.get("pinned"):
            return "pinned"
        if rec.get("blocked_version") == new_v:
            return "blocked"
        if (meta.get("auto_updates") or new_v == "latest") and not opts.greedy:
            return "skipped"
    check_requirements(meta, [])
    log(f"Upgrading {token} {old_v} -> {new_v}" if old_v != new_v else f"Reinstalling {token} {new_v}")

    old_staged = Path(rec["staged"])
    final = caskroom_dir(token, new_v)
    aside = None
    if exists(final):  # same version (reinstall or "latest"): keep the old staging aside
        aside = CASKROOM / token / ".previous"
        remove(aside)
        move(final, aside)
    try:
        stage(meta, final)
        check_bundle_compat(meta, final, opts)
    except BaseException as e:
        remove(final)
        if aside:
            move(aside, final)
        if isinstance(e, CaskError) and ("needs macOS" in str(e) or "has no " in str(e)):
            update_receipt(token, blocked_version=new_v)
            raise CaskError(f"{e}; keeping {old_v} (this version will be skipped from now on)")
        raise

    run_directives(directives(rec["meta"], "uninstall"), aside or old_staged, only=("quit", "signal"))
    backup = CASKROOM / token / ".backup"
    remove(backup)
    backup.mkdir(parents=True)
    saved = []
    for i, it in enumerate(rec["items"]):
        p = Path(it["path"])
        if it["mode"] == "link":
            if p.is_symlink():
                remove(p)
        elif exists(p):
            b = backup / f"{i}-{p.name}"
            move(p, b)
            saved.append((b, p))

    items = []
    uopts = copy.copy(opts)
    uopts.adopt = False
    try:
        install_artifacts(meta, final, uopts, items)
    except BaseException:
        warn("upgrade failed; restoring the previous version")
        rollback(items)
        for b, p in saved:
            move(b, p)
        remove(final)
        if aside:
            move(aside, final)
        for it in rec["items"]:
            if it["mode"] == "link" and it.get("source"):
                try:
                    symlink(Path(it["source"]), Path(it["path"]))
                except CaskError as e:
                    warn(str(e))
        remove(backup)
        raise
    remove(backup)
    if aside:
        remove(aside)
    elif old_staged != final:
        remove(old_staged)
    save_receipt(meta, final, items, keep=rec)
    show_caveats(meta)
    return "upgraded"


@with_appdir
def uninstall(token, opts):
    rec = load_receipt(token)
    if not rec:
        raise CaskError(f"{token} is not installed")
    meta, staged = rec["meta"], Path(rec["staged"])
    log(f"Uninstalling {token} {rec['version']}")
    for kind, _, _ in artifact_entries(meta):
        if kind in ("uninstall_preflight", "uninstall_postflight"):
            warn(f"{token} has a Ruby {kind} block that can't be run")
    run_directives(directives(meta, "uninstall"), staged)
    for it in reversed(rec["items"]):
        p = Path(it["path"])
        try:
            if it["mode"] == "link":
                if p.is_symlink():
                    remove(p)
            elif exists(p):
                log(f"Removing {p}")
                remove(p)
        except CaskError as e:
            warn(str(e))
    if opts.zap:
        log(f"Zapping {token}")
        run_directives(directives(meta, "zap"), staged)
    remove(CASKROOM / token)
    receipt_file(token).unlink()
    log(f"{token} uninstalled")


@with_appdir
def zap(token, opts):
    if load_receipt(token):
        o = copy.copy(opts)
        o.zap = True
        uninstall(token, o)
        return
    meta = fetch_meta(token, opts.offline)
    log(f"Zapping {token} leftovers (the app itself is left alone)")
    run_directives(directives(meta, "zap"), None)


# ---------------------------------------------------------------- CLI

def for_each(tokens, fn):
    failed = []
    for t in tokens:
        try:
            fn(t)
        except KeyboardInterrupt:
            raise
        except Exception as e:  # report and keep going with the other tokens
            if os.environ.get("MYCASK_DEBUG"):
                raise
            print(f"Error: {t}: {e}", file=sys.stderr)
            failed.append(t)
    return failed


def cmd_upgrade(tokens, opts):
    results = {}

    def one(t):
        results[t] = upgrade(t, opts)
        if results[t] == "skipped":
            log(f"{t} updates itself; skipped (use --greedy to include it)")
        elif results[t] == "gone":
            log(f"{t} is no longer in the cask index; keeping the installed version")
        elif results[t] == "pinned":
            log(f"{t} is pinned; skipped")
        elif results[t] == "blocked":
            log(f"{t}: the newest version doesn't support this Mac; staying on the installed one")

    failed = for_each(tokens or installed_tokens(), one)
    if not failed and "upgraded" not in results.values():
        log("Everything is up to date")
    return failed


def cmd_outdated(opts):
    def one(t):
        rec = load_receipt(t)
        try:
            meta = fetch_meta(t, opts.offline)
        except CaskError as e:
            if "no cask named" in str(e):
                print(f"{t} ({rec['version']}) [no longer in the cask index]")
                return
            raise
        new_v = str(meta["version"])
        auto = meta.get("auto_updates") or new_v == "latest"
        if (new_v != rec["version"] or new_v == "latest") and (opts.greedy or not auto):
            tags = [x for x, on in (("auto-updates", auto), ("pinned", rec.get("pinned")),
                    ("unsupported on this Mac", rec.get("blocked_version") == new_v)) if on]
            print(f"{t} ({rec['version']}) != {new_v}" + (f" [{', '.join(tags)}]" if tags else ""))
    return for_each(installed_tokens(), one)


def cmd_info(token, opts):
    meta = fetch_meta(token, opts.offline)
    rec = load_receipt(token)
    print(f"{meta['token']}: {meta['version']}" + (" (auto-updates)" if meta.get("auto_updates") else ""))
    if meta.get("name"):
        print(f"Name: {', '.join(meta['name'])}")
    for key in ("desc", "homepage", "url"):
        if meta.get(key):
            print(f"{key.capitalize()}: {meta[key]}")
    print(f"Installed: {rec['version'] if rec else 'no'}")
    print(f"Artifacts: {', '.join(sorted({k for k, _, _ in artifact_entries(meta)}))}")
    show_caveats(meta)


def cmd_search(query, opts):
    q = query.lower()
    for c in load_index(opts.offline)[0].values():
        hay = " ".join([c.get("token", ""), " ".join(c.get("name") or []), c.get("desc") or ""]).lower()
        if q in hay:
            print(f"{c['token']:<32} {str(c.get('version')):<16} {c.get('desc') or ''}")


def read_bundle(path):
    tokens = []
    for line in Path(path).expanduser().read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            tokens.append(line)
    return tokens


def bundle_entry(line, opts):
    """A cask bundle line, 'token' or 'token --appdir=DIR', -> (token, options for it)."""
    words = shlex.split(line)
    o, rest = copy.copy(opts), words[1:]
    while rest:
        w = rest.pop(0)
        if w.startswith("--appdir="):
            o.appdir = w.split("=", 1)[1]
        elif w == "--appdir" and rest:
            o.appdir = rest.pop(0)
        else:
            raise CaskError(f"unknown option {w!r} in bundle line {line!r}")
    return words[0], o


def main(argv=None):
    if os.geteuid() == 0:
        sys.exit("Don't run mycask as root; it asks for sudo when it needs it")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--offline", action="store_true", help="use cached cask definitions only")
    inst = argparse.ArgumentParser(add_help=False)
    inst.add_argument("--force", action="store_true", help="replace existing files in the way")
    inst.add_argument("--adopt", action="store_true", help="take over apps that are already installed")
    inst.add_argument("--skip-compat", action="store_true",
                      help="don't check the app's own macOS/architecture requirements")
    inst.add_argument("--no-quarantine", dest="quarantine", action="store_false",
                      help="don't mark apps as downloaded from the internet")
    inst.add_argument("--appdir", help=f"folder for the app itself (default {DEFAULT_APPDIR}); "
                                       "upgrades and uninstalls remember it")

    p = argparse.ArgumentParser(prog="mycask", description="Homebrew-cask-compatible app manager")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("install", parents=[common, inst])
    s.add_argument("tokens", nargs="+")
    s = sub.add_parser("reinstall", parents=[common, inst])
    s.add_argument("tokens", nargs="+")
    s = sub.add_parser("upgrade", parents=[common, inst])
    s.add_argument("--greedy", action="store_true", help="include auto-updating casks")
    s.add_argument("tokens", nargs="*")
    s = sub.add_parser("outdated", parents=[common])
    s.add_argument("--greedy", action="store_true")
    s = sub.add_parser("uninstall", parents=[common])
    s.add_argument("--zap", action="store_true", help="also remove settings, caches and support files")
    s.add_argument("tokens", nargs="+")
    s = sub.add_parser("zap", parents=[common])
    s.add_argument("--appdir", help="folder the app was in, for casks mycask didn't install")
    s.add_argument("tokens", nargs="+")
    s = sub.add_parser("update", parents=[common])
    s.add_argument("--force", action="store_true", help="refresh even if the index is under a day old")
    sub.add_parser("list", parents=[common])
    s = sub.add_parser("pin", parents=[common])
    s.add_argument("tokens", nargs="+")
    s = sub.add_parser("unpin", parents=[common])
    s.add_argument("tokens", nargs="+")
    s = sub.add_parser("info", parents=[common])
    s.add_argument("token")
    s = sub.add_parser("search", parents=[common])
    s.add_argument("query")
    s = sub.add_parser("bundle", parents=[common, inst])
    s.add_argument("file")
    args = p.parse_args(argv)
    if sys.platform != "darwin":
        sys.exit("mycask only runs on macOS")
    for name, default in (("force", False), ("adopt", False), ("quarantine", True),
                          ("greedy", False), ("zap", False), ("skip_compat", False), ("appdir", None)):
        if not hasattr(args, name):
            setattr(args, name, default)

    failed = []
    if args.cmd == "install":
        seen = set()
        failed = for_each(args.tokens, lambda t: install(t, args, seen))
    elif args.cmd == "bundle":
        seen = set()
        failed = for_each(read_bundle(args.file), lambda line: install(*bundle_entry(line, args), seen))
    elif args.cmd == "reinstall":
        failed = for_each(args.tokens, lambda t: upgrade(t, args, force=True))
    elif args.cmd == "upgrade":
        failed = cmd_upgrade(args.tokens, args)
    elif args.cmd == "outdated":
        failed = cmd_outdated(args)
    elif args.cmd == "uninstall":
        failed = for_each(args.tokens, lambda t: uninstall(t, args))
    elif args.cmd == "zap":
        failed = for_each(args.tokens, lambda t: zap(t, args))
    elif args.cmd == "update":
        def do_update(_):
            load_index(force=True) if args.force else load_index()
            age = index_age() or 0
            log(f"{len(_INDEX[0])} casks in the index, refreshed {age / 3600:.1f} hours ago")
        failed = for_each(["index"], do_update)
    elif args.cmd == "list":
        for t in installed_tokens():
            rec = load_receipt(t)
            print(f"{t} {rec['version']}" + (" (pinned)" if rec.get("pinned") else ""))
    elif args.cmd in ("pin", "unpin"):
        def flip(t):
            if not load_receipt(t):
                raise CaskError(f"{t} is not installed")
            update_receipt(t, pinned=True if args.cmd == "pin" else None)
        failed = for_each(args.tokens, flip)
    elif args.cmd == "info":
        failed = for_each([args.token], lambda t: cmd_info(t, args))
    elif args.cmd == "search":
        failed = for_each([args.query], lambda q: cmd_search(q, args))
    if failed:
        print(f"Failed: {' '.join(failed)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
