#!/usr/bin/env python3
"""Localization helper for Burrow.

The translation itself lives in Localization/zh-Hans.lproj/Localizable.strings:
a plain "English source" = "中文" table. This script keeps that table in sync
with the Swift sources without ever touching the Mole command-line output.

Usage:
    python3 scripts/localization.py keys              # list English source strings
    python3 scripts/localization.py check             # report missing / stale entries
    python3 scripts/localization.py sync              # add missing keys, drop stale ones

The `sync` command preserves every existing translation, so after pulling a new
upstream version you just run it, translate the newly listed lines, and rebuild.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCES = ROOT / "Sources"
CATALOG = ROOT / "Localization" / "zh-Hans.lproj" / "Localizable.strings"

# The Mole CLI and its parsers stay in English. Translating them would break
# keyword-based parsing ("DRY RUN", "Potential space:", "Items:", ...).
SKIP_DIRS = {"Engine"}
SKIP_FILES = {"ParserTests.swift"}

# Values that are identifiers, file names, symbols, keys or layout tokens,
# not text a person is meant to read.
DENY = {
    "hourglass", "xmark", "checkmark", "touchid", "ellipsis", "arrow.clockwise",
    "info.circle", "exclamationmark.triangle.fill", "gearshape", "trash",
    "doc.text.magnifyingglass", "externaldrive", "folder", "app.dashed",
    "computer", "chart.bar", "cpu", "memorychip", "network", "battery.100",
    "thermometer", "square.and.arrow.up", "pause.circle", "play.circle",
    "chevron.left", "chevron.right", "chevron.down", "chevron.up",
    "line.3.horizontal", "plus", "minus", "magnifyingglass", "square.on.circle",
    "command", "return", "escape", "delete.left", "sidebar.left",
    "en", "zh-Hans", "base", "true", "false", "nil", "default",
    "pill", "pillSecondary", "core", "rim", "plain", "link",
    "graphite", "sage", "violet", "ember", "blue", "orange", "white", "black",
    "GB", "MB", "KB", "TB", "B", "W", "OK",
    "Burrow", "Mole", "macOS", "GitHub", "GPL-3.0", "App Store", "Finder",
    "Contents/Resources/mole", "Library/Logs/mole", ".config/mole/whitelist",
    ".config/mole/purge_paths", "scanPreview", "showInMenuBar",
    "planned-%@", "review-%@", "skipped, ", "y/n", "yyyy-MM-dd HH:mm:ss", "this Mac",
}

# Short words that are still real UI labels.
SHORT_UI = {
    "On", "Off", "OK", "Cancel", "Confirm", "Continue", "Clean", "Stop", "Scan",
    "Start", "Manual", "Skipped", "Remove", "Keep", "Hide", "Show", "All",
    "None", "Back", "Done", "Settings", "History", "Analyze", "Overview",
    "Uninstall", "Projects", "Slim", "Optimize", "Installers", "Yes", "No",
    "Admin", "On", "Off", "Copy", "Open", "Save", "Retry", "Close", "Refresh",
}

STRING = re.compile(r'"((?:[^"\\]|\\.)*)"')


def strip_comments(source: str) -> str:
    """Remove // and /* */ comments while preserving string literals."""
    out: list[str] = []
    i, n = 0, len(source)
    in_string = False
    while i < n:
        c = source[i]
        if in_string:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(source[i + 1])
                i += 2
                continue
            if c == '"':
                in_string = False
            i += 1
            continue
        if c == '"':
            in_string = True
            out.append(c)
            i += 1
            continue
        if source.startswith("//", i):
            while i < n and source[i] != "\n":
                i += 1
            continue
        if source.startswith("/*", i):
            depth = 1
            i += 2
            while i < n and depth:
                if source.startswith("/*", i):
                    depth += 1
                    i += 2
                elif source.startswith("*/", i):
                    depth -= 1
                    i += 2
                else:
                    i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def interpolation_to_placeholder(raw: str) -> str:
    r"""Swift `\(expr)` becomes the `%@` placeholder used in .strings files."""
    out: list[str] = []
    i, n = 0, len(raw)
    while i < n:
        if raw.startswith("\\(", i):
            depth = 1
            i += 2
            while i < n and depth:
                if raw[i] == "(":
                    depth += 1
                elif raw[i] == ")":
                    depth -= 1
                i += 1
            out.append("%@")
            continue
        out.append(raw[i])
        i += 1
    return "".join(out)


def is_display_text(value: str) -> bool:
    if not value or value in DENY:
        return False
    if value != value.strip():
        return False
    if not re.search(r"[A-Za-z]", value):
        return False
    if value.startswith(("/", "~", "$", "http", "#")):
        return False
    if re.fullmatch(r"[A-Za-z0-9_.-]+", value):
        # Bare identifiers: keys, symbol names, built-in commands.
        return value in SHORT_UI or (" " in value)
    if re.fullmatch(r"[a-z]+(?:\.[a-z]+)+", value):
        return False
    # Terminal scraps, regexes and shell snippets are not interface copy.
    if any(token in value for token in ("\\r", "&&", "||", "; do ", "; done", "$(=", "\\s+", "\\u{", "== '", "(Enter|", "[0-9]", "\\b", "--json", "--list")):
        return False
    if value.startswith((")", ",", "·", "⠋", "⠙", "⠹", "⠸", "⠼", "⠴", " ", "%.")):
        return False
    if re.fullmatch(r"(?:%@|%\.\d+f|%d|%s|\s|,|:|·|—)+", value):
        return False
    if len(value) < 3:
        return False
    return True


# A literal used by a parser or a path is not interface copy, even when it
# happens to contain words. Lines that also build a view are always kept.
UI_LINE = re.compile(r"Text\(|Label\(|Button\(|Link\(|\.help\(|Tag\(|alert\(|(?:title|caption|detail|message|button|warning|text|subtitle|label):")
PARSER_LINE = re.compile(
    r"hasPrefix|hasSuffix|replacingOccurrences|components\(separatedBy|range\(of:|\.contains\(|"
    r"NSRegularExpression|pattern:|URL\(string:|UserDefaults\.|Process\(|executableURL|"
    r"FileManager\.|\bpattern\b|\bseparator\b|\bprefix\b|\bsuffix\b|== |!= "
)


def source_keys() -> list[str]:
    keys: set[str] = set()
    for path in sorted(SOURCES.rglob("*.swift")):
        if any(part in SKIP_DIRS for part in path.parts) or path.name in SKIP_FILES:
            continue
        clean = strip_comments(path.read_text(encoding="utf-8"))
        for line in clean.splitlines():
            if PARSER_LINE.search(line) and not UI_LINE.search(line):
                continue
            for match in STRING.finditer(line):
                raw = match.group(1)
                if not is_display_text(raw):
                    continue
                key = interpolation_to_placeholder(raw)
                if key in DENY or not re.search(r"[A-Za-z]", re.sub(r"%@|%\.\d+f", "", key)):
                    continue
                keys.add(key)
    return sorted(keys)


def parse_catalog(path: pathlib.Path) -> tuple[dict[str, str], list[str]]:
    """Very small .strings reader: keeps comments for safe round-tripping."""
    entries: dict[str, str] = {}
    comments: list[str] = []
    if not path.exists():
        return entries, comments
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(r'"((?:[^"\\]|\\.)*)"\s*=\s*"((?:[^"\\]|\\.)*)"\s*;')
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
            comments.append(line)
            continue
        match = pattern.search(line)
        if match:
            entries[unescape(match.group(1))] = unescape(match.group(2))
    return entries, comments


def escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def unescape(value: str) -> str:
    return re.sub(r'\\(.)', lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), m.group(1)), value)


def render(keys: list[str], entries: dict[str, str]) -> str:
    header = [
        "// Burrow 简体中文文案表",
        "// 规则：\"英文原文\" = \"中文译文\";",
        "// 只翻译界面文案。Mole 命令行输出、路径、命令名保持英文，否则解析会失效。",
        "// 新增文案留空即回退英文；运行 python3 scripts/localization.py sync 可自动补全键。",
        "",
    ]
    lines = list(header)
    for key in keys:
        value = entries.get(key, "")
        lines.append(f'"{escape(key)}" = "{escape(value)}";')
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["keys", "check", "sync"])
    args = parser.parse_args()

    keys = source_keys()
    entries, _comments = parse_catalog(CATALOG)
    missing = [k for k in keys if not entries.get(k)]
    stale = [k for k in entries if k not in keys]

    if args.command == "keys":
        print("\n".join(keys))
    elif args.command == "check":
        print(f"Source strings: {len(keys)}  |  translated: {len(keys) - len(missing)}  |  missing: {len(missing)}  |  stale: {len(stale)}")
        if missing:
            print("\nMissing translations:")
            for key in missing:
                print(f"  {key}")
        if stale:
            print("\nStale entries (no longer in source):")
            for key in stale:
                print(f"  {key}")
        return 1 if missing else 0
    else:
        CATALOG.parent.mkdir(parents=True, exist_ok=True)
        CATALOG.write_text(render(keys, entries), encoding="utf-8")
        print(f"Updated {CATALOG.relative_to(ROOT)}: {len(keys)} keys, {len(missing)} untranslated, {len(stale)} removed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
