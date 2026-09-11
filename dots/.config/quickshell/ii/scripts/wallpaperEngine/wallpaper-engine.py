#!/usr/bin/env python3

import argparse
import json
import re
from pathlib import Path


APP_ID = "431960"


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

    project = Path(args.directory).expanduser()
    preview = project_metadata(project)["thumbnailPath"]
    if not preview:
        raise SystemExit(1)
    print(preview)


if __name__ == "__main__":
    main()
