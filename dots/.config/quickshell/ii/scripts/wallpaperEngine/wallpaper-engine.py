#!/usr/bin/env python3

import argparse
import html
import json
import re
from pathlib import Path


APP_ID = "431960"
HTML_TAG_RE = re.compile(r"<[^>]*>")


def steam_libraries():
    candidates = [
        Path.home() / ".local/share/Steam",
        Path.home() / ".steam/steam",
    ]
    library_files = [path / "steamapps/libraryfolders.vdf" for path in candidates]

    for library_file in library_files:
        try:
            content = library_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for value in re.findall(r'"path"\s+"([^"]+)"', content):
            candidates.append(Path(value.replace("\\\\", "\\")))

    seen = set()
    for candidate in candidates:
        resolved = candidate.expanduser()
        key = str(resolved)
        if key not in seen:
            seen.add(key)
            yield resolved


def find_directory(relative_path):
    for library in steam_libraries():
        candidate = library / relative_path
        if candidate.is_dir():
            return candidate
    return None


def workshop_directory():
    return find_directory(f"steamapps/workshop/content/{APP_ID}")


def assets_directory():
    return find_directory("steamapps/common/wallpaper_engine/assets")


def project_preview(project, metadata):
    configured = metadata.get("preview")
    names = [configured] if isinstance(configured, str) else []
    names.extend(
        [
            "preview.jpg",
            "preview.png",
            "preview.jpeg",
            "preview.webp",
            "preview.gif",
            "preview.webm",
            "preview.mp4",
            "screenshot.jpg",
            "screenshot.png",
        ]
    )
    for name in names:
        candidate = project / name
        if candidate.is_file():
            return candidate
    return None


def project_metadata(project):
    metadata_path = project / "project.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        metadata = {}

    title = metadata.get("title")
    wallpaper_type = metadata.get("type")
    preview = project_preview(project, metadata)
    return {
        "filePath": str(project),
        "fileName": str(title) if title else project.name,
        "fileIsDir": False,
        "displayName": str(title) if title else project.name,
        "thumbnailPath": str(preview) if preview else "",
        "wallpaperType": str(wallpaper_type).lower() if wallpaper_type else "unknown",
        "wallpaperEngine": True,
        "workshopId": project.name,
    }


def property_label(name, metadata):
    raw_label = metadata.get("text", metadata.get("label"))
    label = html.unescape(HTML_TAG_RE.sub(" ", str(raw_label or "")))
    label = " ".join(label.split())
    if not label or label.startswith("ui_") or label.startswith("http"):
        label = re.sub(r"[_-]+", " ", name)
    return label.strip().title()


def project_properties(project):
    metadata_path = project / "project.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        raise SystemExit(1)

    definitions = metadata.get("general", {}).get("properties", {})
    properties = []
    supported_types = {
        "bool", "slider", "combo", "color", "textinput", "file", "directory", "scenetexture"
    }
    for name, definition in definitions.items():
        if not isinstance(definition, dict) or definition.get("type") not in supported_types:
            continue
        property_type = definition["type"]
        order = definition.get("order", definition.get("index", 0))
        item = {
            "name": name,
            "label": property_label(name, definition),
            "type": property_type,
            "value": definition.get("value", ""),
            "order": order if isinstance(order, (int, float)) else 0,
        }
        if property_type == "slider":
            minimum = definition.get("min", 0)
            maximum = definition.get("max", 1)
            step = definition.get("step", 0)
            if not isinstance(step, (int, float)) or step <= 0:
                precision = definition.get("precision")
                if isinstance(precision, int) and precision > 0:
                    step = 10 ** -precision
                elif definition.get("fraction") or maximum - minimum <= 10:
                    step = 0.01
                else:
                    step = 1
            item.update({"min": minimum, "max": maximum, "step": step})
        elif property_type == "combo":
            item["options"] = [
                {
                    "label": property_label(str(option.get("value", "")), option),
                    "value": option.get("value"),
                }
                for option in definition.get("options", [])
                if isinstance(option, dict) and "value" in option
            ]
        properties.append(item)

    properties.sort(key=lambda item: (item["order"], item["label"].casefold()))
    project_info = project_metadata(project)
    print(json.dumps({
        "path": str(project),
        "title": project_info["displayName"],
        "properties": properties,
    }, ensure_ascii=True))


def scan(workshop):
    projects = []
    for child in workshop.iterdir():
        if child.is_dir() and (child / "project.json").is_file():
            projects.append(project_metadata(child))
    projects.sort(key=lambda project: project["displayName"].casefold())
    print(json.dumps(projects, ensure_ascii=True))


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    locate_parser = subparsers.add_parser("locate")
    locate_parser.add_argument("kind", choices=("workshop", "assets"))
    scan_parser = subparsers.add_parser("scan")
    scan_parser.add_argument("directory", nargs="?")
    preview_parser = subparsers.add_parser("preview")
    preview_parser.add_argument("directory")
    properties_parser = subparsers.add_parser("properties")
    properties_parser.add_argument("directory")
    classify_parser = subparsers.add_parser("classify")
    classify_parser.add_argument("path")
    args = parser.parse_args()

    if args.command == "locate":
        result = workshop_directory() if args.kind == "workshop" else assets_directory()
        if result is None:
            raise SystemExit(1)
        print(result)
        return

    if args.command == "scan":
        directory = Path(args.directory).expanduser() if args.directory else workshop_directory()
        if directory is None or not directory.is_dir():
            raise SystemExit(1)
        scan(directory)
        return

    if args.command == "classify":
        path = Path(args.path).expanduser()
        if path.is_dir() and (path / "project.json").is_file():
            print("wallpaper-engine")
        elif path.is_dir():
            print("directory")
        elif path.is_file():
            print("file")
        else:
            print("invalid")
        return

    if args.command == "properties":
        project = Path(args.directory).expanduser()
        if not project.is_dir():
            raise SystemExit(1)
        project_properties(project)
        return

    project = Path(args.directory).expanduser()
    preview = project_metadata(project)["thumbnailPath"]
    if not preview:
        raise SystemExit(1)
    print(preview)


if __name__ == "__main__":
    main()
