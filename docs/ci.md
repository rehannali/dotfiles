# CI

`.github/workflows/dotfiles.yml` runs `bootstrap.sh` on an Ubuntu runner (full and cli profile), a macOS Intel runner
and a macOS Apple Silicon runner, then `scripts/check-install.py` looks at what ended up installed. It runs for pull
requests to `main`, pushes to `main`, and when started by hand.

## Manual runs

Actions, dotfiles, Run workflow (or `gh workflow run dotfiles.yml -f key=value`). All inputs are optional.

| Input | Default | Meaning |
|---|---|---|
| `platform` | `all` | `debian`, `debian-cli`, `mac-intel`, `mac-arm` or `all` |
| `casks` | `install` | `install` really installs them, `check` only verifies they can be installed, `skip` |
| `xcode` | `skip` | `install` really installs Xcode with xcodes, see below |
| `xcode_version` | empty | which Xcode; empty means the newest the runner can run |
| `runtime` | `skip` | `install` also downloads the iOS simulator runtime (several GB) |

Pull requests and pushes never install Xcode and never see the Apple secrets.

## Testing the Xcode install on a runner

A runner can't type Apple's two-factor code, so the install uses a fastlane session instead (see
[bitwarden.md](bitwarden.md), "Apple ID for Xcode"). Someone has to log in once to make it. You don't need a Mac for
that, but you do need to pick how.

**1. Make the session.**

- On any machine that has fastlane (`brew install fastlane`):
  ```sh
  fastlane spaceauth -u you@example.com
  ```
  Enter the password and the code Apple sends, copy the long value it prints.
- Or on a runner, with the `apple-session` workflow (Run workflow, give the Apple ID). It installs fastlane and opens
  an SSH terminal for you through tmate, limited to the GitHub user who started it. Run the same command there.
  The terminal goes over the public tmate.io relay, so the code and the session string pass through a server you
  don't run. Use a dedicated Apple ID for this, not your main one.

**2. Save it as a secret** in the repository:

```sh
gh secret set FASTLANE_SESSION          # paste the value, then Ctrl-D
```

Never print the session in a workflow step. This repository is public, and so are its run logs. That is why the
`apple-session` workflow hands you a terminal instead of running the command itself.

**3. Check that it works.** Run the `apple-session-check` workflow. It starts the download of an Xcode with the
session and stops as soon as Apple has accepted the login, so it costs a minute and installs nothing:

```sh
gh workflow run apple-session-check.yml
```

Green means the session is good. Red means it has expired or is wrong, make a new one.

**4. Run the real thing.**

```sh
gh workflow run dotfiles.yml -f platform=mac-arm -f xcode=install -f xcode_version=<version> -f casks=check
```

GitHub's macOS images already have several Xcodes. If you ask for one that is on the image, `xcodes` finds it and
downloads nothing, which doesn't test anything. Look at the image's list and pick a version it doesn't have. With
`xcode_version` empty the newest release the runner can run is used, which may well be on the image already.

**5. Read the result.** The log shows the download and install, and the audit summary has an `xcode` row: it checks
that the Xcode you asked for is selected and that its app is built for the runner's CPU.

## When it fails

- "FASTLANE_SESSION" missing: the secret isn't set. The run stops before anything is installed.
- Apple asks for a code or says the session is invalid: the session has expired (about a month). Make a new one.
- The download is slow or the job runs out of time: the macOS jobs stop after 150 minutes.

The Bitwarden half of the flow (reading the Apple ID from a vault) is not exercised in CI, that would need vault
credentials as secrets. It is tested with a stand-in `bw` in the repo's history instead.
