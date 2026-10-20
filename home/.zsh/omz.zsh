ZSH_THEME="spaceship"
ZSH_DISABLE_COMPFIX="true"
DISABLE_UPDATE_PROMPT="true"
DISABLE_MAGIC_FUNCTIONS=true
ENABLE_CORRECTION="true"
COMPLETION_WAITING_DOTS="true"

# Plugins that wrap a command print an error on every shell start when it is missing, and several of
# these tools are absent on Intel Macs (no mise build, no Homebrew bottle). Load them only when installed.
# Order is unchanged. `mise activate` already ran in .zshrc, so mise-managed tools count as installed.
plugins=()
(( $+commands[poetry] )) && plugins+=(poetry)
plugins+=(
  zsh-autosuggestions
  zsh-256color
  fast-syntax-highlighting
  zsh-autocomplete
)
(( $+commands[lsd] ))     && plugins+=(zsh-lsd)
(( $+commands[bat] ))     && plugins+=(zsh-bat)
(( $+commands[thefuck] )) && plugins+=(thefuck)
plugins+=(
  you-should-use
  ohmyzsh-full-autoupdate
)

source $ZSH/oh-my-zsh.sh