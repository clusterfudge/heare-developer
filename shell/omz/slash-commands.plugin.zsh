#!/usr/bin/env zsh
AGENT_CLI=${AGENT_CLI:-"hdev"}

# Register the slash command handler for commands starting with //
function _slash_command() {
    # If command starts with /, transform it to use AGENT_CLI
    if [[ "$BUFFER" == //* ]]; then
        # Get the command without the leading slash
        local cmd="${BUFFER#//}"
        # Replace the buffer with the transformed command
	BUFFER="${AGENT_CLI} ${cmd}"
        # Execute the command in the buffer
        zle accept-line
    else
        # If not a slash command, execute normally
        zle accept-line
    fi
}

# Create a new ZLE widget
zle -N _slash_command

# Bind the widget to Enter key
bindkey '^M' _slash_command