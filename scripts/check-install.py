#!/usr/bin/env python3
"""Audit this machine after `chezmoi apply`.

    scripts/check-install.py [--source REPO] [--no-shell]

Nothing here trusts the package lists. It asks the machine:

  1. expected tools  What does the dotfiles tool plan say should exist HERE (home/.chezmoitemplates/tool-plan,
                     rendered by chezmoi for this OS/arch)? For each one: does the command resolve in a login
                     zsh (so ~/.zshenv / ~/.zprofile PATH handling is tested too), does it come from the
                     manager that is supposed to provide it (mise / brew / apt, or MacPorts on Intel) and not from a shadowing copy,
                     and does it actually start?
  2. architecture    Every executable and native library under mise, Homebrew, ~/.local/bin, installed Mac
                     apps and gem extensions is classified with `file`: an ELF on macOS, a Mach-O on Linux, or
                     the wrong CPU (x86_64 on Apple Silicon, arm64 on Intel) is a failure.
  3. mise            Every tool in ~/.config/mise/config.toml is installed.
  4. shell           `zsh -i -c exit` starts without errors.

Exit status 1 if anything failed. Warnings (known gaps, e.g. a Homebrew formula with no Intel bottle) do not
fail the run. A Markdown report goes to $GITHUB_STEP_SUMMARY when set. Needs only python3 (3.9+) and the
standard tools `file`, `zsh`; `chezmoi` for the plan.
"""
import argparse
import json
import os
import platform
import plistlib
import re
import shutil
import stat
import subprocess
import sys

OK, WARN, FAIL = "✅", "⚠️", "❌"
HOME = os.path.expanduser("~")
SYSTEM = platform.system()  # Darwin | Linux


def run(cmd, timeout=60, env=None):
    """Run a command, return (returncode, combined output). 124 on timeout, 127 if it cannot be executed."""
    try:
        p = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=timeout, env=env, universal_newlines=True, errors="replace")
        return p.returncode, p.stdout
    except subprocess.TimeoutExpired:
        return 124, "timed out after %ss" % timeout
    except OSError as e:
        return 127, str(e)


def host_arch():
    if SYSTEM == "Darwin":
        # A Rosetta-translated python reports x86_64 on an arm64 Mac; ask the hardware.
        rc, out = run(["sysctl", "-n", "hw.optional.arm64"])
        if rc == 0 and out.strip() == "1":
            return "arm64"
    return "arm64" if platform.machine() in ("arm64", "aarch64") else "x86_64"


ARCH = host_arch()
INTEL_MAC = SYSTEM == "Darwin" and ARCH == "x86_64"
TARGET = "macOS %s" % ("Apple Silicon" if ARCH == "arm64" else "Intel") if SYSTEM == "Darwin" else "Linux %s" % ARCH

findings = []  # (level, section, subject, message)


def add(level, section, subject, message=""):
    findings.append((level, section, subject, message))


# file classification
def classify(desc):
    """`file -b` text -> (format, set of archs) or None for anything that is not a native binary."""
    if "Mach-O" in desc:
        archs = set(re.findall(r"\[(x86_64|arm64e?|i386)", desc))
        if not archs:
            archs = set(re.findall(r"\b(x86_64|arm64e?|i386)\b", desc))
        return "Mach-O", {"arm64" if a.startswith("arm64") else a for a in archs}
    if desc.startswith("ELF"):
        archs = set()
        if "x86-64" in desc:
            archs.add("x86_64")
        if "aarch64" in desc or "ARM aarch64" in desc:
            archs.add("arm64")
        if "Intel 80386" in desc:
            archs.add("i386")
        if "ARM," in desc and "aarch64" not in desc:
            archs.add("arm32")
        return "ELF", archs
    return None


def judge(desc):
    """None if not a native binary, "" if right for this host, else a reason it is wrong."""
    c = classify(desc)
    if c is None:
        return None
    fmt, archs = c
    expected_fmt = "Mach-O" if SYSTEM == "Darwin" else "ELF"
    if fmt != expected_fmt:
        return "%s binary on %s" % (fmt, SYSTEM)
    if ARCH not in archs:
        return "%s only, this machine is %s" % ("/".join(sorted(archs)) or "unknown arch", ARCH)
    return ""


def file_descriptions(paths):
    """{path: `file -L -b` description}, in chunks so thousands of files stay fast."""
    out = {}
    for i in range(0, len(paths), 250):
        chunk = paths[i:i + 250]
        rc, text = run(["file", "-L", "-b", "--"] + chunk, timeout=120)
        lines = text.splitlines()
        if len(lines) == len(chunk):
            out.update(zip(chunk, lines))
        else:  # a filename with a newline or a file error: fall back to one by one
            for p in chunk:
                out[p] = run(["file", "-L", "-b", "--", p])[1].strip()
    return out


def native_candidates(root):
    """Executables and native libraries below root (regular files only; symlinks are visited at their target)."""
    found = []
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            p = os.path.join(dirpath, f)
            try:
                st = os.lstat(p)
            except OSError:
                continue
            if not stat.S_ISREG(st.st_mode) or st.st_size == 0:
                continue
            if st.st_mode & 0o111 or f.endswith((".so", ".dylib", ".bundle")) or ".so." in f:
                found.append(p)
    return found


# environment discovery
def brew_prefix():
    brew = shutil.which("brew")
    for cand in ([brew] if brew else []) + ["/opt/homebrew/bin/brew", "/usr/local/bin/brew"]:
        if cand and os.path.exists(cand):
            rc, out = run([cand, "--prefix"])
            if rc == 0 and out.strip():
                return out.strip().splitlines()[-1]
    return None


MISE = shutil.which("mise") or os.path.join(HOME, ".local", "bin", "mise")
BREW = brew_prefix() if SYSTEM == "Darwin" else None
MISE_DIR = os.path.join(HOME, ".local", "share", "mise")


def manager_of(path):
    if path.startswith(MISE_DIR + os.sep) or "/.local/share/mise/" in path:
        return "mise"
    if BREW and path.startswith(BREW + os.sep):
        return "brew"
    if path.startswith("/opt/local" + os.sep):
        return "macports"
    if path.startswith(("/usr/bin/", "/bin/", "/usr/sbin/", "/sbin/", "/usr/local/bin/", "/usr/games/")):
        return "system"
    return "other"


def mise_installs():
    rc, out = run([MISE, "ls", "--json"], timeout=120)
    if rc != 0:
        add(FAIL, "mise", "mise ls --json", out.strip()[:300])
        return {}
    try:
        return json.loads(out)
    except ValueError:
        add(FAIL, "mise", "mise ls --json", "not JSON")
        return {}


# 1. expected tools
BAD_RUN = re.compile(
    r"Exec format error|Bad CPU type|cannot execute|error while loading shared libraries|Library not loaded|"
    r"dyld\[|dyld:|GLIBC_[0-9.]+' not found|image not found|cannot open shared object|bad interpreter",
    re.I)


VERSION_FLAG = {"tmux": "-V", "go": "version", "zig": "version", "java": "-version", "javac": "-version",
                "git-flow": "version"}


def smoke(path):
    """(level, note): does the command start? Only loader/format errors count; exit codes of --version do not."""
    rc, out = run([path, VERSION_FLAG.get(os.path.basename(path), "--version")], timeout=20)
    first = (out.strip().splitlines() or [""])[0][:60]
    if rc in (126, 127) or BAD_RUN.search(out):
        return FAIL, "does not start: %s" % (out.strip().splitlines() or ["exit %s" % rc])[0][:100]
    if rc == 124:
        return WARN, "no answer to --version in 20s"
    return OK, first


def load_plan(source):
    if not shutil.which("chezmoi"):
        add(WARN, "tools", "plan", "chezmoi not on PATH: expectations skipped")
        return None
    cmd = ["chezmoi"] + (["-S", source] if source else []) + ["execute-template", '{{ includeTemplate "tool-plan" . }}']
    rc, out = run(cmd, timeout=120)
    if rc != 0:
        add(FAIL, "tools", "plan", out.strip()[:300])
        return None
    return json.loads(out)


def check_expected(plan):
    expect = [e for e in plan["expect"] if e["bin"]]
    names = sorted({e["bin"] for e in expect})
    script = 'for b in "$@"; do printf "%s\\t%s\\n" "$b" "$(command -v "$b" 2>/dev/null)"; done'
    shell = shutil.which("zsh") or shutil.which("bash")
    rc, out = run([shell, "-l", "-c", script, "_"] + names, timeout=120)
    resolved = {}
    for line in out.splitlines():
        if "\t" in line:
            name, _, path = line.partition("\t")
            resolved[name] = path.strip()
    rows = []
    for e in sorted(expect, key=lambda x: (x["via"], x["name"])):
        path = resolved.get(e["bin"], "")
        strict = e["kind"] in ("cli", "apple")
        if not path or not os.path.exists(path):
            known_gap = INTEL_MAC and e["via"] == "brew" and not e.get("source") and not e.get("port")
            level = WARN if (known_gap or not strict and INTEL_MAC) else FAIL
            why = "no bottle expected on Intel (Homebrew Tier 3)" if known_gap else "not found on PATH"
            add(level, "tools", e["name"], "%s via %s: %s" % (e["bin"], e["via"], why))
            rows.append((level, e["name"], e["via"], "-", why))
            continue
        real = os.path.realpath(path)
        mgr = manager_of(path) if manager_of(path) != "other" else manager_of(real)
        want = {"mise": "mise", "brew": "brew", "apt": "system"}[e["via"]]
        if e["via"] == "brew" and e.get("port") and mgr == "macports":
            want = "macports"   # Intel: no Homebrew bottle, the MacPorts binary is the planned fallback
        if strict and mgr != want:
            add(FAIL, "tools", e["name"], "%s resolves to %s (%s); expected %s" % (e["bin"], path, mgr, e["via"]))
            rows.append((FAIL, e["name"], e["via"], path, "shadowed by %s copy" % mgr))
            continue
        level, note = smoke(path)
        if level != OK:
            add(level, "tools", e["name"], "%s: %s" % (path, note))
        rows.append((level, e["name"], e["via"], path.replace(HOME, "~"), note))
    libs = [e for e in plan["expect"] if not e["bin"]]
    add(OK, "tools", "libraries", "%d library/dev packages have no command to check" % len(libs))
    return rows


RUNTIME_BINS = ["node", "npm", "python3", "pip3", "ruby", "gem", "java", "javac", "go", "rustc", "cargo", "uv", "mise"]
if SYSTEM == "Darwin":  # gems installed into mise's Ruby by run_onchange_after_13-install-ruby-gems
    RUNTIME_BINS += ["pod", "fastlane"]


def flutter_expected(source):
    """Is a Flutter SDK part of this machine's setup (settings.flutter.version, full profile, not skipped)?"""
    if os.environ.get("DOTFILES_FLUTTER") == "skip" or configured_profile() == "cli" or not shutil.which("chezmoi"):
        return False
    cmd = ["chezmoi"] + (["-S", source] if source else []) + ["execute-template", "{{ .settings.flutter.version }}"]
    rc, out = run(cmd, timeout=60)
    return rc == 0 and bool(out.strip())


def check_runtimes(source=None):
    rows = []
    runtime_bins = RUNTIME_BINS + (["flutter", "dart"] if flutter_expected(source) else [])
    script = 'for b in "$@"; do printf "%s\\t%s\\n" "$b" "$(command -v "$b" 2>/dev/null)"; done'
    shell = shutil.which("zsh") or shutil.which("bash")
    rc, out = run([shell, "-l", "-c", script, "_"] + runtime_bins, timeout=120)
    for line in out.splitlines():
        name, _, path = line.partition("\t")
        if not path:
            add(FAIL, "runtimes", name, "not found on PATH")
            rows.append((FAIL, name, "-", "not found"))
            continue
        if name in ("flutter", "dart") and "/fvm/" not in path:
            add(FAIL, "runtimes", name, "resolves to %s, not the fvm global SDK (~/fvm/default)" % path)
            rows.append((FAIL, name, path.replace(HOME, "~"), "not from fvm"))
            continue
        rc, text = run([path, VERSION_FLAG.get(name, "--version")], timeout=120 if name == "flutter" else 30)
        first = (text.strip().splitlines() or [""])[0][:60]
        if rc in (126, 127) or BAD_RUN.search(text):
            add(FAIL, "runtimes", name, "does not start: %s" % first)
            rows.append((FAIL, name, path.replace(HOME, "~"), first))
        else:
            rows.append((OK, name, path.replace(HOME, "~"), first))
    return rows


# 2. architecture audit
def collect_roots(installs):
    roots = []  # (label, directory-or-file list)
    for tool, entries in sorted(installs.items()):
        for ent in entries:
            if ent.get("installed") and ent.get("install_path") and os.path.isdir(ent["install_path"]):
                roots.append(("mise:%s" % tool, native_candidates(ent["install_path"])))
    if os.path.exists(MISE):
        roots.append(("mise binary", [MISE]))
    if BREW:
        files = []
        for d in ("bin", "sbin"):
            p = os.path.join(BREW, d)
            if os.path.isdir(p):
                files += [os.path.join(p, f) for f in sorted(os.listdir(p))]
        roots.append(("brew bin", [f for f in files if os.path.isfile(f)]))
    lb = os.path.join(HOME, ".local", "bin")
    if os.path.isdir(lb):
        roots.append(("~/.local/bin", [os.path.join(lb, f) for f in sorted(os.listdir(lb))
                                       if os.path.isfile(os.path.join(lb, f))]))
    if shutil.which("mise"):
        rc, out = run([MISE, "exec", "ruby", "--", "gem", "env", "gemdir"], timeout=60)
        gemdir = out.strip().splitlines()[-1] if rc == 0 and out.strip() else ""
        if gemdir and os.path.isdir(gemdir):
            roots.append(("gem extensions", native_candidates(gemdir)))
    return roots


def check_apps():
    """Mac apps (casks / App Store): Apple Silicon can run x86_64 apps via Rosetta, Intel cannot run arm64-only."""
    if SYSTEM != "Darwin":
        return 0
    execs = []
    for base in ("/Applications", os.path.join(HOME, "Applications")):
        if not os.path.isdir(base):
            continue
        for app in sorted(os.listdir(base)):
            if not app.endswith(".app"):
                continue
            try:
                with open(os.path.join(base, app, "Contents", "Info.plist"), "rb") as fh:
                    exe = plistlib.load(fh).get("CFBundleExecutable")
            except Exception:
                continue
            p = os.path.join(base, app, "Contents", "MacOS", exe or "")
            if exe and os.path.isfile(p):
                execs.append(p)
    # runner images ship dozens of apps; only report those that this run could not have run
    descs = file_descriptions(execs)
    for p, d in descs.items():
        c = classify(d)
        if not c or ARCH in c[1]:
            continue
        name = p.split("/Contents/")[0].rsplit("/", 1)[-1]
        if ARCH == "arm64" and "x86_64" in c[1]:
            add(WARN, "apps", name, "x86_64 only: needs Rosetta on Apple Silicon")
        else:
            add(FAIL, "apps", name, "%s only, this Mac is %s" % ("/".join(sorted(c[1])), ARCH))
    return len(execs)


def check_casks(source):
    """Casks from packages.yml: installed, and the .app really sits where the cask was told to put it."""
    if SYSTEM != "Darwin" or os.environ.get("DOTFILES_CASKS", "install") != "install" \
            or os.environ.get("DOTFILES_PROFILE", "full") == "cli":
        return []
    brew = os.path.join(BREW, "bin", "brew") if BREW else shutil.which("brew")
    if not brew or not shutil.which("chezmoi"):
        add(WARN, "casks", "check", "needs brew and chezmoi: skipped")
        return []
    rc, out = run(["chezmoi"] + (["-S", source] if source else []) + [
        "execute-template", "{{ concat .packages.darwin.casks %s | toJson }}" % (
            ".packages.darwin_arm.casks" if ARCH == "arm64" else "(list)")], timeout=120)
    if rc != 0:
        add(FAIL, "casks", "list", out.strip()[:300])
        return []
    wanted = json.loads(out)
    rc, out = run(["chezmoi"] + (["-S", source] if source else []) + [
        "execute-template", '{{ dig "settings" "macos" "cask_appdir" "~/Applications" . }}'], timeout=60)
    cask_appdir = out.strip() if rc == 0 and out.strip() else "~/Applications"
    cask_appdir = os.path.expanduser(cask_appdir)
    rc, out = run([brew, "list", "--cask"], timeout=120)
    installed = set(out.split()) if rc == 0 else set()
    rows = []
    for c in wanted:
        name = c["name"]
        token = name.rsplit("/", 1)[-1]
        appdir = cask_appdir if "appdir" in c.get("args_str", "") else "/Applications"
        if token not in installed:
            add(WARN, "casks", name, "not installed (unsupported or disabled for this Mac, see 'Left out' in the log)")
            rows.append((WARN, name, "-", "not installed"))
            continue
        rc, info = run([brew, "info", "--json=v2", "--cask", name], timeout=120)
        apps = []
        try:
            for art in json.loads(info)["casks"][0].get("artifacts", []):
                if isinstance(art, dict) and art.get("app"):
                    # ["Source.app", {"target": "Name.app"}]: the app is installed under its target name
                    names = [a for a in art["app"] if isinstance(a, str)]
                    targets = [a["target"] for a in art["app"] if isinstance(a, dict) and a.get("target")]
                    apps += targets or names
        except (ValueError, KeyError, IndexError):
            pass
        if not apps:
            rows.append((OK, name, "-", "installed (no .app: font, pkg or binary)"))
            continue
        for app in apps:
            app = os.path.basename(app)
            where = [d for d in dict.fromkeys(("/Applications", os.path.join(HOME, "Applications"), cask_appdir))
                     if os.path.exists(os.path.join(d, app))]
            if not where:
                add(FAIL, "casks", name, "installed but %s is neither in /Applications nor in ~/Applications" % app)
                rows.append((FAIL, name, "-", "%s missing" % app))
            elif os.path.realpath(appdir) not in [os.path.realpath(d) for d in where]:
                add(WARN, "casks", name, "%s is in %s, not in %s" % (app, where[0], appdir))
                rows.append((WARN, name, where[0], "%s not in the appdir" % app))
            else:
                rows.append((OK, name, appdir.replace(HOME, "~"), app))
    add(OK, "casks", "summary", "%d of %d casks installed" % (len([c for c in wanted if c["name"].rsplit("/", 1)[-1] in installed]), len(wanted)))
    return rows


def check_architecture():
    installs = mise_installs()
    summary = []
    total = 0
    for label, paths in collect_roots(installs):
        descs = file_descriptions(paths) if paths else {}
        native = bad = 0
        for p, d in descs.items():
            verdict = judge(d)
            if verdict is None:
                continue
            native += 1
            if verdict:
                bad += 1
                add(FAIL, "architecture", p.replace(HOME, "~"), verdict)
        total += native
        summary.append((FAIL if bad else OK, label, native, bad))
    apps = check_apps()
    return summary, total, apps


# 3. mise, 4. shell
def check_mise():
    rc, out = run([MISE, "ls", "--missing"], timeout=120)
    missing = out.strip()
    if rc != 0:
        add(FAIL, "mise", "mise ls --missing", missing[:300])
    elif missing:
        add(FAIL, "mise", "tools from config.toml that are not installed", missing[:600])
    else:
        add(OK, "mise", "every tool in config.toml is installed")
    # In a login shell, like a real session: from a bare CI step mise rightly complains it is not activated.
    shell = shutil.which("zsh") or shutil.which("bash")
    rc, out = run([shell, "-l", "-c", "mise doctor 2>&1"], timeout=120)
    if "No problems found" in out:
        add(OK, "mise", "mise doctor", "no problems found")
    else:
        detail = out.split("problem", 1)[-1] if "problem" in out else out
        add(WARN, "mise", "mise doctor", " ".join(detail.split())[:400])


NOISE = re.compile(r"command not found|not found|No such file|error|cannot|failed", re.I)


def check_xcode():
    """Only when this run asked for an Xcode install (DOTFILES_XCODE=install, set by the CI for manual runs)."""
    if SYSTEM != "Darwin" or os.environ.get("DOTFILES_XCODE") != "install":
        return
    wanted = os.environ.get("DOTFILES_XCODE_VERSION", "")
    rc, out = run(["xcodes", "installed"], timeout=60)
    if rc != 0:
        add(FAIL, "xcode", "xcodes installed", out.strip()[:200])
        return
    lines = [l for l in out.splitlines() if l.strip()]
    selected = next((l for l in lines if "Selected" in l), "")
    if not selected:
        add(FAIL, "xcode", "selected Xcode", "none is selected; installed: " + "; ".join(l.strip() for l in lines)[:300])
        return
    if wanted and not selected.split()[0].startswith(wanted):
        add(FAIL, "xcode", "selected Xcode", "asked for %s but the selected one is %s" % (wanted, selected.strip()))
        return
    app = next((w for w in selected.split() if w.endswith(".app")), "")
    binary = os.path.join(app, "Contents", "MacOS", "Xcode") if app else ""
    if binary and os.path.exists(binary):
        rc, archs = run(["lipo", "-archs", binary], timeout=30)
        if ARCH not in archs.split():
            add(FAIL, "xcode", app, "built for %s, this Mac is %s" % (archs.strip(), ARCH))
            return
    add(OK, "xcode", "Xcode", selected.strip()[:120])


def configured_profile():
    """full | cli, from the environment or the chezmoi config `chezmoi init` wrote."""
    if os.environ.get("DOTFILES_PROFILE"):
        return os.environ["DOTFILES_PROFILE"]
    try:
        with open(os.path.join(HOME, ".config", "chezmoi", "chezmoi.toml")) as fh:
            m = re.search(r'^\s*profile\s*=\s*"(\w+)"', fh.read(), re.M)
            return m.group(1) if m else "full"
    except OSError:
        return "full"


GUI_PATHS = [".config/alacritty", ".config/wezterm", ".config/karabiner", ".hyper.js"]


def check_profile():
    profile = configured_profile()
    if profile != "cli":
        add(OK, "profile", "full", "everything is installed")
        return
    present = [p for p in GUI_PATHS if os.path.exists(os.path.join(HOME, p))]
    if present:
        add(FAIL, "profile", "cli", "GUI configs present on a cli machine: " + ", ".join(present))
    else:
        add(OK, "profile", "cli", "no GUI app configs (alacritty, wezterm, karabiner, hyper)")
    if SYSTEM == "Darwin":
        apps = [a for base in ("/Applications", os.path.join(HOME, "Applications")) if os.path.isdir(base)
                for a in os.listdir(base) if a.endswith(".app")]
        add(WARN if apps else OK, "profile", "Mac apps", "%d apps installed (runner images ship some)" % len(apps))


def check_shell():
    zsh = shutil.which("zsh")
    if not zsh:
        add(FAIL, "shell", "zsh", "not installed")
        return
    env = dict(os.environ, TERM="xterm-256color", DISABLE_AUTO_UPDATE="true")
    rc, out = run([zsh, "-l", "-i", "-c", "exit"], timeout=180, env=env)
    lines = [l for l in out.splitlines() if NOISE.search(l) and "SPACESHIP" not in l]
    if rc == 124:
        add(WARN, "shell", "zsh -l -i", "did not exit within 180s")
    elif lines:
        add(WARN, "shell", "zsh -l -i -c exit", "; ".join(l.strip() for l in lines[:5])[:500])
    else:
        add(OK, "shell", "zsh -l -i -c exit", "starts without errors")


# report
def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c).replace("|", "\\|") for c in r) + " |" for r in rows]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--source", help="chezmoi source (repo) to read the tool plan from; default: chezmoi's own")
    ap.add_argument("--no-shell", action="store_true", help="skip the interactive zsh check")
    args = ap.parse_args()

    md = ["# Dotfiles install audit: %s" % TARGET, ""]
    md.append("Host: `%s` · brew prefix: `%s` · mise: `%s`" % (platform.platform(), BREW or "none", MISE))

    plan = load_plan(args.source)
    tool_rows = check_expected(plan) if plan else []
    runtime_rows = check_runtimes(args.source)
    cask_rows = check_casks(args.source)
    arch_rows, native_total, apps = check_architecture()
    check_mise()
    check_profile()
    check_xcode()
    if not args.no_shell:
        check_shell()

    fails = [f for f in findings if f[0] == FAIL]
    warns = [f for f in findings if f[0] == WARN]
    md += ["", "**%s %d failed · %s %d warnings · %d native binaries/libraries checked for %s%s**" % (
        FAIL, len(fails), WARN, len(warns), native_total, TARGET, " · %d Mac apps" % apps if SYSTEM == "Darwin" else "")]
    if fails:
        md += ["", "## Failures", table(["", "area", "subject", "detail"], [(f[0], f[1], f[2], f[3]) for f in fails])]
    if warns:
        md += ["", "## Warnings", table(["", "area", "subject", "detail"], [(f[0], f[1], f[2], f[3]) for f in warns])]
    if tool_rows:
        md += ["", "## Expected tools (%d)" % len(tool_rows),
               table(["", "tool", "via", "resolved", "version / note"], tool_rows)]
    if cask_rows:
        md += ["", "## Casks (%d)" % len(cask_rows), table(["", "cask", "where", "note"], cask_rows)]
    md += ["", "## Runtimes", table(["", "command", "resolved", "version"], runtime_rows)]
    md += ["", "## Architecture", table(["", "origin", "native files", "wrong"], arch_rows)]

    report = "\n".join(md) + "\n"
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as fh:
            fh.write(report + "\n")
    for level, section, subject, message in fails:  # GitHub annotations
        if os.environ.get("GITHUB_ACTIONS"):
            print("::error title=%s %s::%s: %s" % (TARGET, section, subject, message.replace("\n", " ")))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
