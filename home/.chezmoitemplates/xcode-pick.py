#!/usr/bin/env python3
"""Pick the Xcode, and the matching iOS simulator runtime, that this Mac can actually run.

    xcode-pick.py xcode                  newest released Xcode for this Mac, e.g. 26.6
    xcode-pick.py runtime --xcode 26.6   iOS runtime that goes with that Xcode, e.g. 26.5

`xcodes install --latest` only warns when the newest Xcode needs a newer macOS than the one you have, and then
installs it anyway. An Intel Mac, which stops at macOS 26, would get an Xcode 27 it can't open. So the choice is
made here from the xcodereleases.com data: only plain releases (no beta, no release candidate), whose required
macOS is not newer than this one and whose download supports this CPU.

xcodes also has its own view of what suits a Mac: `xcodes list` shows only [Universal] builds on an Intel Mac and
only [Apple Silicon] builds on an Apple Silicon Mac (override with --architecture). Pass that output with
--listed and only versions it lists are considered, so the pick is one xcodes itself offers for this CPU. xcodes
does not look at the macOS version, which is why the check above stays.

Options for testing: --macos 26.6 --arch x86_64 --data some-data.json --listed xcodes-list.txt
Prints one line on stdout and exits 0, or prints nothing and exits 1 when nothing fits or the data can't be read.
"""
import argparse
import json
import re
import subprocess
import sys
import urllib.request

URL = "https://xcodereleases.com/data.json"


def numbers(text):
    return tuple(int(n) for n in re.findall(r"\d+", text or ""))


def at_most(a, b):
    """a <= b as version numbers, so that 26.6 equals 26.6.0"""
    a, b = list(numbers(a)), list(numbers(b))
    size = max(len(a), len(b))
    return a + [0] * (size - len(a)) <= b + [0] * (size - len(b))


def command(*args):
    try:
        return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, universal_newlines=True).stdout.strip()
    except OSError:
        return ""


def this_arch():
    # a Rosetta process reports x86_64 on an Apple Silicon Mac, so ask the hardware
    return "arm64" if command("sysctl", "-n", "hw.optional.arm64") == "1" else "x86_64"


def download(entry):
    return (entry.get("links") or {}).get("download") or {}


def is_release(entry):
    kind = entry["version"]["release"]
    return kind.get("release") is True and len(kind) == 1


def usable(entry, macos, arch):
    required = entry.get("requires")
    if required and not at_most(required, macos):
        return False
    archs = download(entry).get("architectures")
    return not archs or arch in archs


def normal(text):
    """26.6 and 26.6.0 are the same version: drop trailing zeros"""
    parts = list(numbers(text))
    while parts and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def listed_releases(text):
    """Versions of the released (not beta, RC or GM) rows in `xcodes list` output, e.g. `26.6 (17F113) [Universal]`."""
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    found = set()
    for line in text.splitlines():
        row = re.match(r"^\s*(\d+(?:\.\d+){0,2})([^(]*)\(", line)
        if row and not row.group(2).strip():
            found.add(normal(row.group(1)))
    return found


def candidates(data, macos, arch, listed=None):
    found = [e for e in data if is_release(e) and usable(e, macos, arch)]
    if listed:
        found = [e for e in found if normal(e["version"]["number"]) in listed]
    return sorted(found, key=lambda e: (numbers(e["version"]["number"]), e.get("_dateOrder", 0)), reverse=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("what", choices=["xcode", "runtime"])
    ap.add_argument("--xcode", help="for runtime: the Xcode version it has to go with")
    ap.add_argument("--macos", help="default: this Mac's macOS version")
    ap.add_argument("--arch", choices=["arm64", "x86_64"], help="default: this Mac's CPU")
    ap.add_argument("--data", help="read this file instead of downloading xcodereleases.com/data.json")
    ap.add_argument("--listed", help="output of `xcodes list --architecture ...`; only the releases in it are considered")
    args = ap.parse_args()

    macos = args.macos or command("sw_vers", "-productVersion")
    arch = args.arch or this_arch()
    try:
        if args.data:
            with open(args.data) as fh:
                data = json.load(fh)
        else:
            with urllib.request.urlopen(URL, timeout=30) as response:
                data = json.load(response)
    except (OSError, ValueError) as err:
        print("cannot read the Xcode release data: %s" % err, file=sys.stderr)
        return 1

    listed = None
    if args.listed:
        try:
            with open(args.listed) as fh:
                listed = listed_releases(fh.read())
        except OSError:
            listed = None
        if not listed:
            print("no usable `xcodes list` output, going by the release data alone", file=sys.stderr)
    found = candidates(data, macos, arch, listed)
    if args.what == "xcode":
        if not found:
            print("no Xcode release fits macOS %s on %s" % (macos, arch), file=sys.stderr)
            return 1
        print(found[0]["version"]["number"])
        return 0

    if not args.xcode:
        print("runtime needs --xcode", file=sys.stderr)
        return 1
    for entry in found:
        if numbers(entry["version"]["number"]) == numbers(args.xcode):
            sdks = sorted(numbers(s["number"]) for s in (entry.get("sdks") or {}).get("iOS", []))
            if sdks:
                print(".".join(str(n) for n in sdks[-1]))
                return 0
    print("no iOS SDK known for Xcode %s" % args.xcode, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
