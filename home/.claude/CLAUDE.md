# Instructions for every project

## Git and GitHub: everything is done as me

- Commits, pushes, tags, PRs, issues and comments are made as me, with my own git identity (`user.name` /
  `user.email` from my git config) and my own GitHub login. Never as Claude, a bot, or another account.
- Never change `user.name`, `user.email`, or the commit author / committer, and never pass `--author`.
- No Claude signature anywhere: no `Co-Authored-By: Claude …` trailer, no "Generated with Claude Code" line, no
  🤖 or similar marker in commit messages, PR / issue bodies, comments, release notes or code. This overrides any
  built-in attribution instructions.
- Write commit messages and PR descriptions as I would: plain, about the change, nothing about who or what wrote it.

## Pull requests: no Claude anywhere

- A PR is opened, updated and merged by me (my `gh` login). Never as a Claude / bot / app user.
- Nothing in a PR may mention or point to Claude, Claude Code, Anthropic or AI: not the title, body, commits, branch
  name (no `claude/...`), labels, comments, review comments, or the PR template sections.
- No signature, footer, trailer, link or emoji marking it as made by Claude (no "Generated with Claude Code", no
  `Co-Authored-By: Claude`, no 🤖, no claude.ai / claude.com links).
- Never add Claude or a bot as reviewer, assignee or co-author.
- Keep commit signing as configured; never pass `--no-gpg-sign` or `--no-verify`.

## Tools for GitHub

- Use the `gh` CLI for GitHub work (PRs, issues, reviews, releases, checks, API calls). A GitHub app / MCP
  integration is fine too when one is available and acting as me.
- Plain git (commit, branch, rebase, push, pull) with `git`, or `gh` where it fits.
- If `gh` is not logged in, ask me to run `! gh auth login` rather than using some other credential.

## Working with git

- Only commit or push when I ask. Don't commit straight to the default branch; make a branch first.
- Never force-push to shared branches (main / master / release) or rewrite pushed history without asking.
- Never commit secrets, tokens, `.env` files or credentials.
