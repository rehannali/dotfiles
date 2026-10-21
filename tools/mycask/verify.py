#!/usr/bin/env python3
"""Check that mycask really installed everything a list asks for. Standard library only (macOS system Python 3.9).

    python3 -I tools/mycask/verify.py --formulae tools/mycask/intel/formulae.txt
    python3 -I tools/mycask/verify.py --casks tools/mycask/intel/casks.txt [--markdown FILE]

It reads mycask's receipts, not its output, so it also catches an install that reported success and left nothing.

  formula   has a receipt; its keg exists; every link it made exists; every command it links into bin/ starts
            (a loader error such as "Library not loaded", "Bad CPU type" or "dyld" fails; a non-zero exit of --version
            does not); its runtime dependencies have receipts too
  cask      has a receipt; every app, binary and other item it placed exists; every command it linked starts

Exit status 1 when anything is missing or broken. The report is a Markdown table (stdout, and --markdown FILE).
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("MYCASK_ROOT", "~/.local/share/mycask")).expanduser()
FPREFIX = Path(os.environ.get("MYCASK_FORMULA_PREFIX", "/usr/local")).expanduser()
CELLAR = FPREFIX / "Cellar"
LOADER_ERRORS = ("dyld", "Library not loaded", "Bad CPU type", "cannot execute", "Exec format error",
                 "image not found", "no suitable image")
# commands that must not be started to look at them (they open a UI, wait for input or change the system)
SKIP_SMOKE = {"sudo", "reboot", "shutdown", "login", "su"}


def entries(path):
    out = []
    for line in Path(path).read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            out.append(line.split()[0])
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


def check_formula(name, rows):
    rec = load(ROOT / "formula-receipts" / ("%s.json" % name))
    if rec is None:
        rows.append((name, "formula", "FAIL", "not installed (no receipt)"))
        return False
    problems = []
    if rec.get("source") in ("homebrew", "ci"):
        keg = CELLAR / name / str(rec.get("pkg_version"))
        if not keg.is_dir():
            problems.append("keg %s is missing" % keg)
        links = rec.get("links") or []
        gone = [l for l in links if not os.path.lexists(l) or not os.path.exists(l)]
        if gone:
            problems.append("%d of %d links are broken (%s)" % (len(gone), len(links), gone[0]))
        for l in links:
            p = Path(l)
            if p.parent == FPREFIX / "bin" and os.path.exists(l):
                why = starts(p)
                if why:
                    problems.append("%s %s" % (p.name, why))
        for dep in rec.get("deps") or []:
            if load(ROOT / "formula-receipts" / ("%s.json" % dep)) is None:
                problems.append("dependency %s is not installed" % dep)
        note = "%s via %s, %d links" % (rec.get("pkg_version"), rec.get("source"), len(links))
    else:
        note = "via %s (%s)" % (rec.get("source"), rec.get("spec"))
    rows.append((name, "formula", "FAIL" if problems else "ok", "; ".join(problems) or note))
    return not problems


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


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--formulae", help="file with one formula per line")
    ap.add_argument("--casks", help="file with one cask token per line (a trailing --appdir=... is ignored)")
    ap.add_argument("--markdown", help="also write the report to this file")
    args = ap.parse_args()
    if not (args.formulae or args.casks):
        ap.error("pass --formulae and/or --casks")
    rows, ok = [], True
    for n in entries(args.formulae) if args.formulae else []:
        ok &= check_formula(n, rows)
    for t in entries(args.casks) if args.casks else []:
        ok &= check_cask(t, rows)
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
