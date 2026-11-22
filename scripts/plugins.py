"""Check plugin sources, publish versioned archives, and generate the market index."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
SLUG = r"[a-z0-9]+(?:-[a-z0-9]+)*"
NUM = r"(?:0|[1-9][0-9]*)"
PRERELEASE = rf"(?:{NUM}|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
VERSION = rf"{NUM}\.{NUM}\.{NUM}(?:-{PRERELEASE}(?:\.{PRERELEASE})*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
TAG = re.compile(rf"({SLUG})/v({VERSION})")
SHA256 = re.compile(r"[0-9a-f]{64}")
MARKER = "\n\n<!-- axonhub-registry\n"


def command(*args, capture=False):
    result = subprocess.run(args, cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE if capture else None)
    return result.stdout.strip() if capture else None


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def identity(manifest):
    fields = ("id", "name", "description", "version", "axonhubVersion")
    values = {field: manifest.get(field, "") for field in fields}
    if any(not isinstance(value, str) for value in values.values()):
        raise ValueError("Invalid manifest metadata")
    for field in ("id", "name", "version", "axonhubVersion"):
        if not values[field].strip():
            raise ValueError(f"Missing manifest field: {field}")
    if not re.fullmatch(VERSION, values["version"]):
        raise ValueError(f"{values['id']}: invalid semantic version")
    return values


def plugin_sources():
    sources = {}
    ids = set()
    for path in sorted((ROOT / "plugins").glob("*/manifest.json")):
        slug = path.parent.name
        metadata = identity(read_json(path))
        if not re.fullmatch(SLUG, slug) or metadata["id"] in ids:
            raise ValueError(f"Invalid plugin directory or duplicate plugin ID: {path.parent}")
        sources[slug] = metadata
        ids.add(metadata["id"])
    return sources


def read_external(managed_ids):
    entries = read_json(ROOT / "external-plugins.json")["plugins"]
    ids = set(managed_ids)
    for entry in entries:
        plugin_id = entry["id"]
        if not plugin_id.strip() or not entry["name"].strip() or plugin_id in ids:
            raise ValueError(f"Missing metadata or duplicate plugin ID: {plugin_id}")
        ids.add(plugin_id)
        versions = set()
        if not entry["versions"]:
            raise ValueError(f"No versions for {plugin_id}")
        for item in entry["versions"]:
            url = urlsplit(item["url"])
            version = item["version"]
            if (
                not re.fullmatch(VERSION, version)
                or version in versions
                or not SHA256.fullmatch(item["sha256"])
                or not item["axonhubVersion"].strip()
                or url.scheme != "https"
                or not url.hostname
                or url.username is not None
            ):
                raise ValueError(f"Invalid or duplicate external version: {plugin_id} {version}")
            versions.add(version)
    return entries


def pack(slug, metadata, directory):
    asset = Path(directory) / f"{slug}-{metadata['version']}.axplugin"
    packer = os.environ.get("PACK_PLUGIN", "pack-plugin")
    command(packer, str(ROOT / "plugins" / slug), "-o", str(asset))
    with ZipFile(asset) as archive:
        if identity(json.loads(archive.read("manifest.json"))) != metadata:
            raise ValueError(f"{asset.name}: manifest differs from plugin source")
    return asset


def check(sources):
    with TemporaryDirectory() as directory:
        for slug, metadata in sources.items():
            tests = sorted((ROOT / "plugins" / slug).rglob("*.test.mjs"))
            if tests:
                command("node", "--test", *map(str, tests))
            pack(slug, metadata, directory)


def releases(repository):
    pages = json.loads(command("gh", "api", "--paginate", "--slurp", f"repos/{repository}/releases?per_page=100", capture=True))
    return {
        release["tag_name"]: release
        for page in pages for release in page
        if TAG.fullmatch(release["tag_name"])
    }


def notes(metadata, digest, summary):
    return summary + MARKER + json.dumps({**metadata, "sha256": digest}, ensure_ascii=False) + "\n-->\n"


def release_metadata(release):
    tag = release["tag_name"]
    _, version = TAG.fullmatch(tag).groups()
    _, marker, metadata = (release["body"] or "").rpartition(MARKER)
    if not marker or not metadata.rstrip().endswith("\n-->"):
        raise ValueError(f"{tag}: missing registry metadata")
    metadata = json.loads(metadata.rstrip().removesuffix("\n-->"))
    if identity(metadata)["version"] != version or not SHA256.fullmatch(metadata["sha256"]):
        raise ValueError(f"{tag}: invalid registry metadata")
    return metadata


def release_asset(release, metadata):
    tag = release["tag_name"]
    slug, version = TAG.fullmatch(tag).groups()
    name = f"{slug}-{version}.axplugin"
    for asset in release["assets"]:
        if asset["name"] == name:
            if asset["state"] != "uploaded" or asset.get("digest") != f"sha256:{metadata['sha256']}":
                raise ValueError(f"{tag}: GitHub asset digest or state differs from release metadata")
            return asset["browser_download_url"]
    return None


def publish_asset(repository, existing, slug, metadata, asset, summary):
    version = metadata["version"]
    tag = f"{slug}/v{version}"
    if existing and not existing["draft"]:
        raise ValueError(f"{tag}: version is already published")
    digest = hashlib.sha256(asset.read_bytes()).hexdigest()
    opts = ["--repo", repository]
    if existing:
        previous = release_metadata(existing)
        if previous != {**metadata, "sha256": digest}:
            raise ValueError(f"{tag}: pending release contains different bytes; publish a new version")
        for pending in existing["assets"]:
            if pending["name"] == asset.name and pending["state"] == "starter":
                command("gh", "api", "--method", "DELETE", f"repos/{repository}/releases/assets/{pending['id']}")
        existing["assets"] = [item for item in existing["assets"] if item["state"] != "starter"]
        if not release_asset(existing, previous):
            command("gh", "release", "upload", tag, str(asset), *opts)
    else:
        command(
            "gh", "release", "create", tag, str(asset), *opts, "--draft", "--latest=false",
            "--target", command("git", "rev-parse", "HEAD", capture=True),
            "--title", f"{metadata['name']} {version}", "--notes", notes(metadata, digest, summary),
        )
    release = releases(repository)[tag]
    if not release_asset(release, release_metadata(release)):
        raise ValueError(f"{tag}: missing package")
    command("gh", "release", "edit", tag, *opts, "--draft=false", "--latest=false")


def publish(repository, sources):
    existing = releases(repository)
    with TemporaryDirectory() as directory:
        for slug, metadata in sources.items():
            tag = f"{slug}/v{metadata['version']}"
            current = existing.get(tag)
            if current and not current["draft"]:
                if release_metadata(current)["id"] != metadata["id"]:
                    raise ValueError(f"{tag}: plugin ID changed")
                continue
            asset = pack(slug, metadata, directory)
            publish_asset(repository, current, slug, metadata, asset, metadata["description"])


def version_key(version):
    core, _, prerelease = version.split("+", 1)[0].partition("-")
    identifiers = tuple((0, int(part)) if part.isdigit() else (1, part) for part in prerelease.split(".")) if prerelease else ()
    return tuple(map(int, core.split("."))), not prerelease, identifiers


def registry(repository, sources, external):
    published = {}
    for tag, release in sorted(releases(repository).items()):
        if release["draft"]:
            continue
        slug, version = TAG.fullmatch(tag).groups()
        metadata = release_metadata(release)
        url = release_asset(release, metadata)
        if not url:
            raise ValueError(f"{tag}: published release is missing its package")
        published.setdefault(slug, []).append((metadata, {
            "version": version, "url": url, "sha256": metadata["sha256"], "axonhubVersion": metadata["axonhubVersion"],
        }))
    entries = []
    for slug, versions in sorted(published.items()):
        versions.sort(key=lambda release: version_key(release[1]["version"]), reverse=True)
        latest = versions[0][0]
        if len({metadata["id"] for metadata, _ in versions}) > 1:
            raise ValueError(f"{slug}: published versions use different plugin IDs")
        entries.append({
            **{key: latest[key] for key in ("id", "name", "description")},
            "versions": [version for _, version in versions],
        })
    all_entries = entries + external
    ids = {entry["id"] for entry in all_entries}
    if len(ids) != len(all_entries):
        raise ValueError("Duplicate plugin ID across published releases and external plugins")
    for slug, metadata in sources.items():
        if not any(item["version"] == metadata["version"] and src["id"] == metadata["id"] for src, item in published.get(slug, [])):
            raise ValueError(f"{slug}: source version {metadata['version']} has not been published")
    (ROOT / "registry.json").write_text(
        json.dumps({"schemaVersion": 1, "plugins": all_entries}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("check", "publish", "registry"))
    args = parser.parse_args()
    sources = plugin_sources()
    external = read_external(metadata["id"] for metadata in sources.values())
    if args.action == "check":
        check(sources)
    else:
        repository = os.environ["GITHUB_REPOSITORY"]
        if args.action == "publish":
            publish(repository, sources)
        registry(repository, sources, external)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
