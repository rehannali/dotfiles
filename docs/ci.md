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
[bitwarden.md](bitwarden.md), "Apple ID for Xcode"). Someone has to sign in once to make it. The session grants
access to an Apple account, so this is a credential and is handled like one: it only ever lives in a repository
**secret**, never in an Actions variable (variables are plain text) and never in a log.

### One-time setup (this is a public repository)

```sh
# 1. who may start the session workflows, and who may open the terminal
gh variable set APPLE_SESSION_USER --body "$(gh api user -q .login)"

# 2. the environment the session job runs in, with you as the required reviewer, and only on main
gh api -X PUT repos/{owner}/{repo}/environments/apple-session --input - <<JSON
{"reviewers":[{"type":"User","id":$(gh api user -q .id)}],
 "deployment_branch_policy":{"protected_branches":false,"custom_branch_policies":true}}
JSON
gh api -X POST repos/{owner}/{repo}/environments/apple-session/deployment-branch-policies -f name=main -f type=branch
```

Then in the repository settings:

- Settings, Actions, General: set "Fork pull request workflows from outside collaborators" to **Require approval for
  all outside collaborators**, and leave "Send write tokens / secrets to workflows from pull requests" **off**.
  Workflow permissions: read only (the workflows ask for `contents: read` themselves).
- Settings, Collaborators: nobody else. Anyone with write access can start these workflows or edit them.
- Settings, Branches: protect `main` (require a pull request), so a workflow can't be changed behind your back.
- Use a dedicated Apple ID for this, not your main one.

What stops anyone else from using the session workflow:

1. `guard` job: fails unless the person who started it is `APPLE_SESSION_USER`.
2. The terminal only accepts the SSH keys on that GitHub user's profile (`limit-access-to-users`).
3. The `apple-session` environment makes the job wait for your approval before it starts.
4. Fork pull requests never receive secrets, and the Apple workflows can't be started from a pull request at all.
5. The two third-party actions are pinned to an exact commit, not a movable tag.

### Make the session and save it

Run the `apple-session` workflow from `main` (Actions, apple-session, Run workflow; the environment only allows
`main`; give the Apple ID), approve the run if you set yourself as the reviewer, and:

1. Open the log of the last step ("Open a terminal for you"). After about a minute it prints an
   `ssh ...@uptermd.upterm.dev` line. Run it from your own terminal (WSL is fine). It needs the private key that
   goes with an SSH public key on your GitHub profile.
2. In the terminal on the runner:
   ```sh
   gh auth login -w      # shows a code; approve it at github.com/login/device in your browser
   get-session           # Apple password, then the code Apple sends to your device
   ```
   `get-session` stores the value straight into the secret `FASTLANE_SESSION` and deletes it from the runner.
   (If you run it before logging in to GitHub it tells you to log in and run `save-session`.)
3. `exit`. If nobody connects within 15 minutes the run ends on its own.
4. Revoke the temporary GitHub login: github.com/settings/applications, "GitHub CLI" (or just delete the
   authorization). The runner is thrown away, but the token should not outlive the session.

Or make it on your own machine with `scripts/apple-session.sh you@example.com --save`, no relay involved.

### Which relay: the default server or your own

By default the terminal goes through upterm's public relay, `uptermd.upterm.dev`, run by the upterm project.

- **What it protects:** the action checks the relay's host key against a key shipped with the action, so nobody can
  stand in for it. Only the SSH keys you allowed can open the session.
- **What you trust it with:** the relay is a third-party server that carries the whole terminal: your Apple
  password, the two-factor code and the session value pass through it. I could not find a statement in upterm's
  documentation that the relay cannot read the session, so assume it can. That is why a dedicated Apple ID is
  advised, and why the session is short-lived (a month) and can be revoked by changing the Apple ID password.
- **Fine for:** a one-off with a dedicated Apple ID. **Not fine for:** anything you would not give to a stranger
  running the server.

With your own relay, only your server carries the traffic. Deploy `uptermd` (Fly.io, Kubernetes with helm, or Docker;
see upterm's "Deployment" section), then set two Actions variables and the workflow uses it automatically:

```sh
gh variable set UPTERM_SERVER --body "wss://your-app.fly.dev"
gh variable set UPTERM_KNOWN_HOSTS --body '@cert-authority [your-app.fly.dev]:443 ssh-ed25519 AAAA...'
```

`UPTERM_KNOWN_HOSTS` is the public host key of your server. The action refuses to connect to any non-default server
without it, so it can't be tricked into talking to something else. A `wss://` address means port 443 and needs the
`[host]:443` form shown above; `ssh://host:22` needs the plain host. Unset both variables to go back to the default.
The tradeoff: you now run and patch a server. For a handful of sessions a year, the default relay with a dedicated
Apple ID is usually the more sensible risk.

### Check it, then use it

```sh
gh workflow run apple-session-check.yml                 # starts an Xcode download with the secret, stops after login
gh workflow run dotfiles.yml -f platform=mac-arm -f xcode=install -f xcode_version=<version> -f casks=check
```

The check costs a minute and installs nothing. Green means the session works; red means it expired or is wrong.

GitHub's macOS images already have several Xcodes. If you ask for one that is on the image, `xcodes` finds it and
downloads nothing, which doesn't test anything. Look at the image's list and pick a version it doesn't have. With
`xcode_version` empty the newest release the runner can run is used, which may well be on the image already.

The audit summary of the install run has an `xcode` row: it checks that the Xcode you asked for is selected and
that its app is built for the runner's CPU.

When you are done testing, `gh secret delete FASTLANE_SESSION` removes the credential.

## When it fails

- "FASTLANE_SESSION" missing: the secret isn't set. The run stops before anything is installed.
- Apple asks for a code or says the session is invalid: the session has expired (about a month). Make a new one.
- The download is slow or the job runs out of time: the macOS jobs stop after 150 minutes.

The Bitwarden half of the flow (reading the Apple ID from a vault) is not exercised in CI, that would need vault
credentials as secrets. It is tested with a stand-in `bw` in the repo's history instead.
