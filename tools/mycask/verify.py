#!/usr/bin/env python3
"""Check that every cask a list asks for is really installed. Standard library only (macOS system Python 3.9).

    python3 -I tools/mycask/verify.py --casks tools/mycask/intel/casks.txt [--markdown FILE]          mycask
    python3 -I tools/mycask/verify.py --brew --casks tools/mycask/arm64/casks.txt [--markdown FILE]   Homebrew

mycask: it reads mycask's receipts, not its output, so it also catches an install that reported success and left
nothing; every app, binary and other item the cask placed must exist. Homebrew: `brew info --json=v2` must say the
cask is installed, and each app must be in the folder the line names (--appdir=DIR, else /Applications) and each
binary linked into Homebrew's bin. Both: every command a cask links must start (a loader error such as "Library not
loaded", "Bad CPU type" or "dyld" fails; a non-zero exit of --version does not).

Exit status 1 when anything is missing or broken. The report is a Markdown table (stdout, and --markdown FILE).
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("MYCASK_ROOT", "~/.local/share/mycask")).expanduser()
LOADER_ERRORS = ("dyld", "Library not loaded", "Bad CPU type", "cannot execute", "Exec format error",
                 "image not found", "no suitable image")
# commands that must not be started to look at them (they open a UI, wait for input or change the system)
SKIP_SMOKE = {"sudo", "reboot", "shutdown", "login", "su"}


def entries(path):
    """[(token, appdir or None)] of a casks.txt ("token" or "token --appdir=DIR")."""
    out = []
    for line in Path(path).read_text().splitlines():
        words = line.split("#", 1)[0].split()
        if words:
            appdir = next((w.split("=", 1)[1] for w in words[1:] if w.startswith("--appdir=")), None)
            out.append((words[0], os.path.expanduser(appdir) if appdir else None))
    return out


def load(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def starts(exe):
    """'' if the command starts (any exit status), else why not."""
    if exe.name in SKIP_SMOKE:
        return ""
    for flag in ("--version", "-h"):
        try:
            p = subprocess.run([str(exe), flag], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=15,
                               env={**os.environ, "HOME": os.environ.get("HOME", "/tmp"), "NO_COLOR": "1"})
        except subprocess.TimeoutExpired:
            return ""   # it started and kept running
        except OSError as e:
            return "cannot be started: %s" % e
        text = (p.stdout or "") + (p.stderr or "")
        bad = [m for m in LOADER_ERRORS if m in text]
        if bad:
            return "%s: %s" % (bad[0], text.strip().splitlines()[0][:160])
        if p.returncode == 0:
            return ""
    return ""


def check_cask(token, rows):
    rec = load(ROOT / "receipts" / ("%s.json" % token))
    if rec is None:
        rows.append((token, "cask", "FAIL", "not installed (no receipt)"))
        return False
    problems, items = [], rec.get("items") or []
    for it in items:
        path = it.get("path")
        if path and not os.path.lexists(path):
            problems.append("%s %s is missing" % (it.get("kind"), path))
        elif path and it.get("kind") == "binary":
            if not os.path.exists(path):
                problems.append("binary %s points nowhere" % path)
            else:
                why = starts(Path(path))
                if why:
                    problems.append("%s %s" % (Path(path).name, why))
    kinds = sorted({str(i.get("kind")) for i in items})
    note = "%s: %s" % (rec.get("version"), ", ".join(kinds) if kinds else "installer only (pkg)")
    rows.append((token, "cask", "FAIL" if problems else "ok", "; ".join(problems) or note))
    return not problems


def check_brew_cask(token, appdir, rows):
    """Homebrew (Apple Silicon): installed, apps in their folder, linked commands start."""
    p = subprocess.run(["brew", "info", "--json=v2", "--cask", token], capture_output=True, text=True)
    try:
        meta = json.loads(p.stdout)["casks"][0]
    except (ValueError, KeyError, IndexError):
        rows.append((token, "cask", "FAIL", "brew info failed: %s" % (p.stderr.strip().splitlines() or ["?"])[-1][:160]))
        return False
    if not meta.get("installed"):
        rows.append((token, "cask", "FAIL", "not installed"))
        return False
    prefix = subprocess.run(["brew", "--prefix"], capture_output=True, text=True).stdout.strip() or "/opt/homebrew"
    problems, kinds = [], []
    for art in meta.get("artifacts") or []:
        if not isinstance(art, dict):
            continue
        for kind, args in art.items():
            kinds.append(kind)
            args = args if isinstance(args, list) else [args]
            names = [a for a in args if isinstance(a, str)]
            targets = [a["target"] for a in args if isinstance(a, dict) and a.get("target")]
            if kind in ("app", "suite") and names:
                name = os.path.basename(targets[0] if targets else names[0])
                folder = appdir or "/Applications"
                if not os.path.exists(os.path.join(folder, name)):
                    problems.append("%s is not in %s" % (name, folder))
            elif kind == "binary" and names:
                link = Path(prefix) / "bin" / os.path.basename(targets[0] if targets else names[0])
                if not link.exists():
                    problems.append("binary %s is missing" % link)
                else:
                    why = starts(link)
                    if why:
                        problems.append("%s %s" % (link.name, why))
    shown = sorted({k for k in kinds if k not in ("uninstall", "zap", "uninstall_postflight", "uninstall_preflight")})
    note = "%s: %s" % (meta.get("installed"), ", ".join(shown) or "installer only")
    rows.append((token, "cask", "FAIL" if problems else "ok", "; ".join(problems) or note))
    return not problems


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--casks", help="file with one cask token per line, optionally followed by --appdir=DIR")
    ap.add_argument("--brew", action="store_true", help="check Homebrew's casks (Apple Silicon) instead of mycask's")
    ap.add_argument("--markdown", help="also write the report to this file")
    args = ap.parse_args()
    if not args.casks:
        ap.error("pass --casks")
    rows, ok = [], True
    for token, appdir in entries(args.casks):
        ok &= check_brew_cask(token, appdir, rows) if args.brew else check_cask(token, rows)
    bad = [r for r in rows if r[2] != "ok"]
    out = ["| | kind | status | detail |", "|---|---|---|---|"]
    out += ["| %s | %s | %s | %s |" % (n, k, s, d.replace("|", "\\|")) for n, k, s, d in sorted(rows, key=lambda r: (r[2] == "ok", r[1], r[0]))]
    out += ["", "%d of %d verified, %d failed" % (len(rows) - len(bad), len(rows), len(bad))]
    text = "\n".join(out)
    print(text)
    if args.markdown:
        Path(args.markdown).write_text(text + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
