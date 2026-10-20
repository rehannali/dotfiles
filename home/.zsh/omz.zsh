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

# zsh-autocomplete keeps helper functions in Completions/ (_autocomplete__unambiguous, ...) and puts that directory on
# fpath only when its plugin file is sourced, which Oh My Zsh does after compinit. Then compinit never registers them
# and Tab prints "command not found: _autocomplete__should_insert_unambiguous". Put it on fpath before compinit.
fpath=( $ZSH/custom/plugins/zsh-autocomplete/Completions(N/) $fpath )

# Oh My Zsh caches the completion functions it found in $ZSH_COMPDUMP and only rebuilds that cache when Oh My Zsh
# itself or the plugin list changes, so a plugin update that adds completion functions would not be seen. Rebuild it
# when any plugin has a completion file newer than the cache. (A few stats per shell start.)
ZSH_COMPDUMP="${ZDOTDIR:-$HOME}/.zcompdump-${HOST%%.*}-${ZSH_VERSION}"
() {
  local newer=( $ZSH/custom/plugins/*/{Completions/,}_*(N.e:'[[ $REPLY -nt $ZSH_COMPDUMP ]]':) )
  (( $#newer )) && command rm -f "$ZSH_COMPDUMP" "$ZSH_COMPDUMP.zwc"
}

source $ZSH/oh-my-zsh.sh