# Use the generated color scheme

path=("$HOME/.local/bin" $path)

if test -f ~/.local/state/quickshell/user/generated/terminal/sequences.txt; then
    cat ~/.local/state/quickshell/user/generated/terminal/sequences.txt
fi
