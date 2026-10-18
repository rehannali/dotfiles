# Aliases only replace a command when its replacement is installed. On Intel Macs several of these
# tools are absent (no bottle, no mise build), and an unguarded `alias cd=z` or `alias ls=eza` would
# break the shell.
command -v nvim >/dev/null 2>&1 && alias vi="nvim"
command -v zoxide >/dev/null 2>&1 && alias cd="z"
alias zshconfig="nvim ~/.zshrc"
alias zshenvconfig="nvim ~/.zshenv"
# alias vimconfig="nvim ~/.vimrc"
alias tmuxconfig="nvim ~/.tmux.conf"
alias aliasconfig="nvim ~/.zsh/aliases.zsh"
alias omzconfig="nvim ~/.zsh/omz.zsh"
alias szsh="source ~/.zshrc"
if command -v eza >/dev/null 2>&1; then
    alias ls="eza --icons=always --group-directories-first --color=always --git --long --no-filesize --no-time --no-user --no-permissions"
    alias ll="eza --icons=always --group-directories-first --color=always --git --long -l"
fi
