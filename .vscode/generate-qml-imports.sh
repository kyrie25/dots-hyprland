#!/usr/bin/env bash
set -euo pipefail

workspace_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source_dir="$workspace_dir/dots/.config/quickshell/ii"
import_dir="$workspace_dir/.vscode/qml-imports"

mkdir -p "$import_dir"

# Quickshell provides `qs` virtually at runtime. Mirror its imported directories
# as standard QML modules so qmlls can discover their QML types.
while IFS= read -r module; do
    module_path=${module//./\/}
    module_source="$source_dir/${module_path#qs/}"
    module_output="$import_dir/$module_path"

    [[ -d "$module_source" ]] || continue
    mkdir -p "$module_output"

    {
        printf 'module %s\n' "$module"

        while IFS= read -r qml_file; do
            file_name=$(basename "$qml_file")
            type_name=${file_name%.qml}
            ln -sfn "$qml_file" "$module_output/$file_name"

            if rg -q '^pragma Singleton' "$qml_file"; then
                printf 'singleton %s 1.0 %s\n' "$type_name" "$file_name"
            else
                printf '%s 1.0 %s\n' "$type_name" "$file_name"
            fi
        done < <(find "$module_source" -maxdepth 1 -type f -name '*.qml' | sort)
    } > "$module_output/qmldir"

    while IFS= read -r js_file; do
        ln -sfn "$js_file" "$module_output/$(basename "$js_file")"
    done < <(find "$module_source" -maxdepth 1 -type f -name '*.js' | sort)
done < <(
    rg --no-filename '^import qs\.[A-Za-z0-9_.]+' "$source_dir" --glob '*.qml' \
        | sed -E 's/^import (qs\.[A-Za-z0-9_.]+).*/\1/' \
        | sort -u
)
