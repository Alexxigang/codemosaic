from __future__ import annotations

import argparse
import fnmatch
import json
import mimetypes
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXTENSION_DIR = ROOT / "extensions" / "vscode"
DEFAULT_DIST_DIR = ROOT / "dist"
DEFAULT_IGNORE = [".vscode/**", ".git/**", "node_modules/**", "**/__pycache__/**"]
CONTENT_TYPE_DEFAULTS = {
    ".json": "application/json",
    ".js": "application/javascript",
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".yml": "text/yaml",
    ".yaml": "text/yaml",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Package the VS Code extension prototype into a VSIX file.")
    parser.add_argument("--extension-dir", type=Path, default=DEFAULT_EXTENSION_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_DIST_DIR)
    parser.add_argument("--version-suffix", type=str, default=None)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = package_extension(
        extension_dir=args.extension_dir.resolve(),
        output_dir=args.output_dir.resolve(),
        version_suffix=args.version_suffix,
        overwrite=args.overwrite,
    )
    print(output)
    return 0


def package_extension(
    extension_dir: Path,
    output_dir: Path,
    version_suffix: str | None = None,
    overwrite: bool = False,
) -> Path:
    manifest = json.loads((extension_dir / "package.json").read_text(encoding="utf-8"))
    version = str(manifest["version"])
    if version_suffix:
        version = f"{version}-{version_suffix}"
    package_name = f"{manifest['name']}-{version}.vsix"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / package_name
    if output_file.exists() and not overwrite:
        raise FileExistsError(f"output already exists: {output_file}")

    files = collect_extension_files(extension_dir)
    extra_assets = collect_extra_assets()
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        manifest_file = temp_root / "extension.vsixmanifest"
        content_types_file = temp_root / "[Content_Types].xml"
        manifest_file.write_text(
            build_vsix_manifest(
                package_json=manifest,
                version=version,
                include_readme=any(relative == "README.md" for relative, _ in files),
                include_license=any(relative == "LICENSE" for relative, _ in extra_assets),
            ),
            encoding="utf-8",
            newline="\n",
        )
        content_types_file.write_text(build_content_types(files, extra_assets), encoding="utf-8", newline="\n")

        with ZipFile(output_file, "w", compression=ZIP_DEFLATED) as archive:
            archive.write(manifest_file, arcname="extension.vsixmanifest")
            archive.write(content_types_file, arcname="[Content_Types].xml")
            for relative, file_path in files:
                archive.write(file_path, arcname=f"extension/{relative}")
            for relative, file_path in extra_assets:
                archive.write(file_path, arcname=f"extension/{relative}")
    return output_file


def collect_extension_files(extension_dir: Path) -> list[tuple[str, Path]]:
    ignore_patterns = DEFAULT_IGNORE + load_vscodeignore(extension_dir)
    items: list[tuple[str, Path]] = []
    for path in sorted(extension_dir.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(extension_dir).as_posix()
        if matches_any(relative, ignore_patterns):
            continue
        items.append((relative, path))
    return items


def collect_extra_assets() -> list[tuple[str, Path]]:
    items: list[tuple[str, Path]] = []
    license_file = ROOT / "LICENSE"
    if license_file.exists():
        items.append(("LICENSE", license_file))
    return items


def load_vscodeignore(extension_dir: Path) -> list[str]:
    ignore_file = extension_dir / ".vscodeignore"
    if not ignore_file.exists():
        return []
    patterns: list[str] = []
    for line in ignore_file.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        patterns.append(value)
    return patterns


def matches_any(relative_path: str, patterns: list[str]) -> bool:
    name = Path(relative_path).name
    for pattern in patterns:
        normalized = pattern.replace("\\", "/")
        if fnmatch.fnmatch(relative_path, normalized) or fnmatch.fnmatch(f"./{relative_path}", normalized):
            return True
        if "/" not in normalized and fnmatch.fnmatch(name, normalized):
            return True
    return False


def build_vsix_manifest(
    package_json: dict[str, object],
    version: str,
    include_readme: bool,
    include_license: bool,
) -> str:
    package = ET.Element(
        "PackageManifest",
        {
            "Version": "2.0.0",
            "xmlns": "http://schemas.microsoft.com/developer/vsx-schema/2011",
            "xmlns:d": "http://schemas.microsoft.com/developer/vsx-schema-design/2011",
        },
    )
    metadata = ET.SubElement(package, "Metadata")
    identity = ET.SubElement(
        metadata,
        "Identity",
        {
            "Language": "en-US",
            "Id": f"{package_json['publisher']}.{package_json['name']}",
            "Version": version,
            "Publisher": str(package_json["publisher"]),
        },
    )
    identity.tail = "\n"
    ET.SubElement(metadata, "DisplayName").text = str(package_json.get("displayName", package_json["name"]))
    ET.SubElement(metadata, "Description").text = str(package_json.get("description", ""))
    ET.SubElement(metadata, "Tags").text = ",".join(package_json.get("categories", []))
    ET.SubElement(metadata, "Categories").text = "Programming Languages"
    if package_json.get("license"):
        ET.SubElement(metadata, "License").text = str(package_json["license"])
    installation = ET.SubElement(package, "Installation")
    ET.SubElement(
        installation,
        "InstallationTarget",
        {"Id": "Microsoft.VisualStudio.Code", "Version": str(package_json["engines"]["vscode"])}
    )
    ET.SubElement(package, "Dependencies")
    assets = ET.SubElement(package, "Assets")
    ET.SubElement(
        assets,
        "Asset",
        {
            "Type": "Microsoft.VisualStudio.Code.Manifest",
            "d:Source": "File",
            "Path": "extension/package.json",
        },
    )
    if include_readme:
        ET.SubElement(
            assets,
            "Asset",
            {
                "Type": "Microsoft.VisualStudio.Services.Content.Details",
                "d:Source": "File",
                "Path": "extension/README.md",
            },
        )
    if include_license:
        ET.SubElement(
            assets,
            "Asset",
            {
                "Type": "Microsoft.VisualStudio.Services.Content.License",
                "d:Source": "File",
                "Path": "extension/LICENSE",
            },
        )
    xml_bytes = ET.tostring(package, encoding="utf-8", xml_declaration=True)
    return xml_bytes.decode("utf-8")


def build_content_types(
    files: list[tuple[str, Path]],
    extra_assets: list[tuple[str, Path]],
) -> str:
    root = ET.Element("Types", {"xmlns": "http://schemas.openxmlformats.org/package/2006/content-types"})
    seen_extensions: set[str] = set()
    for extension, content_type in sorted(CONTENT_TYPE_DEFAULTS.items()):
        ET.SubElement(root, "Default", {"Extension": extension.lstrip('.'), "ContentType": content_type})
        seen_extensions.add(extension.lower())
    ET.SubElement(root, "Default", {"Extension": "xml", "ContentType": "application/xml"})
    ET.SubElement(root, "Override", {"PartName": "/extension.vsixmanifest", "ContentType": "text/xml"})
    ET.SubElement(root, "Override", {"PartName": "/[Content_Types].xml", "ContentType": "application/xml"})
    for relative, _ in files + extra_assets:
        extension = Path(relative).suffix.lower()
        if not extension or extension in seen_extensions or extension == ".xml":
            continue
        content_type = mimetypes.types_map.get(extension, "application/octet-stream")
        ET.SubElement(root, "Default", {"Extension": extension.lstrip('.'), "ContentType": content_type})
        seen_extensions.add(extension)
    xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return xml_bytes.decode("utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
