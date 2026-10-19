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
| `skip_casks` | `netbird-ui` | casks to leave out, space separated (netbird-ui starts a system service with sudo and stalls on a runner) |
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

Optional, but it saves the GitHub login in the terminal on every run. The runner's own token cannot write secrets,
so it needs a token of yours. Make a **fine-grained personal access token** at
github.com/settings/personal-access-tokens/new: only this repository, repository permission **Secrets: Read and
write** (nothing else; "Metadata: read" is added by itself), and a short expiry. Store it as a secret of the
`apple-session` environment, so only this job can read it, and only after you approved the run:

```sh
gh secret set SECRETS_WRITE_TOKEN --env apple-session      # run inside the clone, paste the token when asked
```

That token can create and delete this repository's secrets but not read them or touch the code. It is narrower
than the login `gh auth login -w` hands out (repo, read:org, gist), which is why it is the better way. If you
skip it, the workflow still works, you just log in to GitHub in the terminal each time.

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
5. The one third-party action (upterm) is pinned to an exact commit, not a movable tag.

### Make the session and save it

Run the `apple-session` workflow from `main` (Actions, apple-session, Run workflow; the environment only allows
`main`; give the Apple ID), approve the run if you set yourself as the reviewer, and:

1. Open the log of the last step ("Open a terminal for you"). After about a minute it prints an
   `ssh ...@uptermd.upterm.dev` line. Run it from your own terminal (WSL is fine), not from a server. It needs the
   private key that goes with an SSH public key on your GitHub profile.

   With your own relay over `wss://` the line is `ssh -o ProxyCommand='upterm proxy '\''***upterm.example.com:443'\''' TOKEN@upterm.example.com:443`.
   The `***` is GitHub hiding the join URL (it contains the session token), so that command cannot be pasted
   as it is. The token is in plain sight as the part before the `@` at the end. Use it yourself (needs the `upterm`
   program installed, `ssh://` relays and the public relay do not):
   ```sh
   TOKEN='AbCdEf...:Wzo6XToyMjEyMw=='        # the part before the last @, copied from the log
   upterm join "wss://$TOKEN@upterm.example.com"
   ```
2. In the terminal on the runner:
   ```sh
   get-session           # Apple password, then the code Apple sends to your device
   ```
   `get-session` stores the value straight into the secret `FASTLANE_SESSION` and deletes it from the runner.
   Without `SECRETS_WRITE_TOKEN` it first says so, and you log in once with `gh auth login -w` (a code you
   approve at github.com/login/device) and run `save-session`.
   If the token was refused (expired), `save-session` says so; `rm ~/.apple-session/token`, log in with
   `gh auth login -w` and run `save-session` again. The session is kept until it has been saved.
3. `exit`. If nobody connects within 15 minutes the run ends on its own.
4. If you logged in with `gh auth login -w`, revoke that login: github.com/settings/applications, "GitHub CLI".
   The runner is thrown away, but the token should not outlive the session. A `SECRETS_WRITE_TOKEN` just expires.

fastlane comes from Homebrew (`brew install fastlane`, which brings its own Ruby), so there is no Ruby to set up and
no third-party Ruby action in the job.

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

### Using your own relay

Then only a machine of yours carries the traffic. You need three things: a server running `uptermd` with a host key
that does not change, the address of that server, and that host key written down for the runner to check.

1. **Make the host key.** `uptermd` makes a new random key every time it starts unless you give it one, and a
   key that changes can't be pinned. So make one and keep the private half on the server only, never in the repo:
   ```sh
   ssh-keygen -t ed25519 -N '' -C uptermd -f uptermd_host_key
   ```
2. **Run the server**, one of:
   - Any VPS with Docker. Port 2222 here so it does not fight the machine's own sshd:
     ```sh
     docker run -d --name uptermd --restart unless-stopped -p 2222:2222 \
       -e PRIVATE_KEY="$(cat uptermd_host_key)" \
       ghcr.io/owenthereal/upterm/uptermd:latest --ssh-addr 0.0.0.0:2222
     ```
     Open TCP 2222 in the firewall.
   - Fly.io: copy `fly.example.toml` from the upterm repository to `fly.toml`, change `app`, then
     `fly secrets set PRIVATE_KEY="$(cat uptermd_host_key)"` and `fly deploy`. It listens on port 22 (ssh) and 443
     (websocket) at `your-app.fly.dev`.
   - Kubernetes: the helm chart (`helm repo add upterm https://upterm.dev`, `helm install uptermd upterm/uptermd`).
   `uptermd` reads the key from the environment variable `PRIVATE_KEY` (the key text) or from files named with
   `--private-key`.
3. **Write the host key down.** It is one line, the server name followed by the public key, in the format of an
   OpenSSH `known_hosts` file. The name is `host` for port 22 and `[host]:port` for any other port (and `[host]:443`
   for a `wss://` address):
   ```sh
   echo "[your.host.name]:2222 $(cut -d' ' -f1,2 uptermd_host_key.pub)"
   ```
4. **Tell the workflow**, with two Actions variables (a public key is not a secret, a variable is fine):
   ```sh
   gh variable set UPTERM_SERVER      --body "ssh://your.host.name:2222"
   gh variable set UPTERM_KNOWN_HOSTS --body "[your.host.name]:2222 ssh-ed25519 AAAA..."
   ```
   Use `ssh://` where you can. With `wss://your-app.fly.dev` your own machine needs the `upterm` program to join
   (the log prints the command); with `ssh://` plain `ssh` is enough.
5. **The first time you connect** from your own machine, `ssh` asks whether to trust the server's key. Compare what it
   shows with `ssh-keygen -lf uptermd_host_key.pub`, and only then say yes.

The action refuses to connect to any other server than the default without `UPTERM_KNOWN_HOSTS`, and it aborts if the
server presents a different key, so it can't be sent somewhere else. The plain-key line needs upterm 0.38.0 or newer
on the runner, which is what the action installs unless told otherwise. To go back to the default relay:
`gh variable delete UPTERM_SERVER; gh variable delete UPTERM_KNOWN_HOSTS`.

The cost is that you now run and patch a server. For a handful of sessions a year, the default relay with a
dedicated Apple ID is often the more sensible risk. I wrote the steps above from upterm's code and documentation and
have not deployed a relay myself.

### Check it, then use it

```sh
gh workflow run apple-session-check.yml                 # starts an Xcode download with the secret, stops after login
gh workflow run apple-session-check.yml -f runner=intel  # the same on the Intel runner (macOS 15, x86_64)
gh workflow run dotfiles.yml -f platform=mac-arm -f xcode=install -f xcode_version=<version> -f casks=check
```

The check costs a minute and installs nothing. Green means the session works; red means it expired or is wrong
(read the output first, it can also be something else). It prints which Xcode and iOS runtime the dotfiles would
install on that runner, picked by the same script as a real install, so running it for `arm` and for `intel` shows
the two choices side by side.

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
