# bw: the Bitwarden CLI, unlocked on first use in this shell with the login bootstrap.sh kept in the macOS Keychain /
# Linux Secret Service (dotfiles-secret). The session stays in this shell only; `bw lock` ends it. Without a kept
# login this is plain bw. Read by ~/.zshrc and ~/.bashrc.
bw() {
  local session rc
  if [ -z "${BW_SESSION:-}" ] && command -v dotfiles-secret > /dev/null 2>&1; then
    case "${1:-}" in
      "" | login | logout | config | lock | status | update | completion | help | --help | -h | --version | -v) ;;
      *) session="$(dotfiles-secret bw-session 2> /dev/null)" && [ -n "$session" ] && export BW_SESSION="$session" ;;
    esac
  fi
  command bw "$@"
  rc=$?
  case "${1:-}" in lock | logout) unset BW_SESSION ;; esac
  return $rc
}
