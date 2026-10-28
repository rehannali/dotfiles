# mise: runtime versions and mise-managed CLI tools (replaces rvm/sdkman/pyenv/rbenv).
# Shims first so non-interactive bash (IDEs, scripts) finds them; `mise activate` adds the real paths.
export PATH="$HOME/.local/share/mise/shims:$HOME/.local/bin:$PATH"
command -v mise >/dev/null 2>&1 && eval "$(mise activate bash)"

# tokens: the Bitwarden fields named like variables (GITHUB_TOKEN), or kept from the environment (secrets.yml)
[ -f "$HOME/.config/dotfiles/secrets.zsh" ] && . "$HOME/.config/dotfiles/secrets.zsh"
# bw unlocks itself with the login bootstrap.sh kept (Keychain / Secret Service)
[ -f "$HOME/.config/shell/bitwarden.sh" ] && . "$HOME/.config/shell/bitwarden.sh"
