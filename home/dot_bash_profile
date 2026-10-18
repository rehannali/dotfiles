# Homebrew (macOS only; the prefix differs between Apple Silicon and Intel)
for brew_bin in /opt/homebrew/bin/brew /usr/local/bin/brew; do
  if [ -x "$brew_bin" ]; then eval "$("$brew_bin" shellenv)"; break; fi
done
unset brew_bin

[ -f "$HOME/.bashrc" ] && . "$HOME/.bashrc"
