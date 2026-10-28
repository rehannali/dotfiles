local wezterm = require('wezterm')
local act = wezterm.action

return {
    keys = {
        -- Shift+Enter: a new line instead of submit in Claude Code, Codex and other TUIs. Sent as ESC+Enter (what
        -- Option+Enter sends), which also gets through tmux unchanged.
        { key = 'Enter', mods = 'SHIFT', action = act.SendString('\x1b\r') },
    },
}
