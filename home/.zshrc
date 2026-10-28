# Runtime versions and the mise-managed CLI tools. First, so that everything below (oh-my-zsh plugins,
# aliases, completions) sees the real tool paths. Replaces pyenv/rbenv/sdkman.
command -v mise >/dev/null 2>&1 && eval "$(mise activate zsh)"

# your environment variables and tokens are loaded by ~/.zshenv (secrets.zsh), for every zsh
# bw unlocks itself with the login bootstrap.sh kept (Keychain / Secret Service)
[[ -f "$HOME/.config/shell/bitwarden.sh" ]] && source "$HOME/.config/shell/bitwarden.sh"

[[ -f "$HOME/.zsh/omz.zsh" ]] && source "$HOME/.zsh/omz.zsh"
[[ -f "$HOME/.zsh/aliases.zsh" ]] && source "$HOME/.zsh/aliases.zsh"
[[ -f "$HOME/.zsh/functions.zsh" ]] && source "$HOME/.zsh/functions.zsh"
[[ -f "$HOME/.zsh/starship.zsh" ]] && source "$HOME/.zsh/starship.zsh"
[[ -f "$HOME/.zsh/history.zsh" ]] && source "$HOME/.zsh/history.zsh"
[[ -f "$HOME/.iterm2_shell_integration.zsh" ]] && source "$HOME/.iterm2_shell_integration.zsh"
[[ -d "$HOME/.iterm2" ]] && path+=("$HOME/.iterm2")   # iTerm2's utilities: imgcat, it2copy, it2dl, ...

# Only initialise tools that are installed (faster startup, same file on every OS)
command -v zoxide  >/dev/null 2>&1 && eval "$(zoxide init zsh)"
command -v atuin   >/dev/null 2>&1 && eval "$(atuin init zsh)"
command -v thefuck >/dev/null 2>&1 && { eval "$(thefuck --alias)"; eval "$(thefuck --alias fk)"; }
command -v uv      >/dev/null 2>&1 && eval "$(uv generate-shell-completion zsh)"
command -v uvx     >/dev/null 2>&1 && eval "$(uvx --generate-shell-completion zsh)"
#eval "$(starship init zsh)"

## [Completion]
## Completion scripts setup. Remove the following line to uninstall
[[ -f "$HOME/.dart-cli-completion/zsh-config.zsh" ]] && . "$HOME/.dart-cli-completion/zsh-config.zsh" || true
## [/Completion]
