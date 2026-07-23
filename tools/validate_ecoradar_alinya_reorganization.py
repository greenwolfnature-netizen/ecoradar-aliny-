#!/usr/bin/env python3
"""Validate that the reorganized Alinyà web retains the original content and controls."""

from __future__ import annotations

import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path


def normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def embedded_data(html: str) -> dict:
    match = re.search(r"\bconst D = (\{.*?\});", html, re.S)
    if not match:
        raise ValueError("No s'ha trobat el paquet de dades incrustat")
    return json.loads(match.group(1))


class AuditParser(HTMLParser):
    fragment_tags = {"p", "li", "td", "th", "summary"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.internal_links: list[str] = []
        self.modes: list[str] = []
        self.layers: list[str] = []
        self.fragments: list[str] = []
        self.visible_parts: list[str] = []
        self.details_count = 0
        self.tables_count = 0
        self._hidden_depth = 0
        self._excluded_depth = 0
        self._captures: list[tuple[str, list[str]]] = []

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = dict(attrs_list)
        if tag in {"script", "style"}:
            self._hidden_depth += 1
        if tag in {"header", "nav"}:
            self._excluded_depth += 1
        if attrs.get("id"):
            self.ids.append(str(attrs["id"]))
        href = attrs.get("href")
        if href and href.startswith("#"):
            self.internal_links.append(href)
        classes = set((attrs.get("class") or "").split())
        if "eu-mode" in classes and attrs.get("data-mode"):
            self.modes.append(str(attrs["data-mode"]))
        if "eu-layer" in classes and attrs.get("data-layer"):
            self.layers.append(str(attrs["data-layer"]))
        if tag == "details":
            self.details_count += 1
        if tag == "table":
            self.tables_count += 1
        if (
            tag in self.fragment_tags
            and "eu-section-kicker" not in classes
            and not self._hidden_depth
            and not self._excluded_depth
        ):
            self._captures.append((tag, []))

    def handle_endtag(self, tag: str) -> None:
        if tag in self.fragment_tags and self._captures and self._captures[-1][0] == tag:
            _, parts = self._captures.pop()
            text = normalized(" ".join(parts))
            for sentence in re.split(r"(?<=[.!?])\s+", text):
                sentence = normalized(sentence)
                if len(sentence) >= 20:
                    self.fragments.append(sentence)
        if tag in {"header", "nav"} and self._excluded_depth:
            self._excluded_depth -= 1
        if tag in {"script", "style"} and self._hidden_depth:
            self._hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._hidden_depth:
            return
        self.visible_parts.append(data)
        for _, parts in self._captures:
            parts.append(data)


def parse_html(html: str) -> AuditParser:
    parser = AuditParser()
    parser.feed(html)
    return parser


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("original", type=Path)
    parser.add_argument("reorganized", type=Path)
    args = parser.parse_args()

    original_html = args.original.read_text(encoding="utf-8")
    reorganized_html = args.reorganized.read_text(encoding="utf-8")
    original = parse_html(original_html)
    reorganized = parse_html(reorganized_html)

    original_fragments = original.fragments
    reorganized_text = normalized(" ".join(reorganized.visible_parts))
    missing_fragments = [fragment for fragment in original_fragments if fragment not in reorganized_text]

    original_modes = original.modes
    new_modes = reorganized.modes
    original_layers = original.layers
    new_layers = reorganized.layers
    ids = reorganized.ids
    internal_links = reorganized.internal_links
    missing_targets = [href for href in internal_links if href[1:] not in ids]
    required_order = ["resum", "cartografia", "mosaic", "biodiversitat", "aigua", "pressions", "foc", "gestio", "fonts"]
    positions = {section_id: reorganized_html.find(f'id="{section_id}"') for section_id in required_order}

    checks = {
        "embedded_data_identical": embedded_data(original_html) == embedded_data(reorganized_html),
        "all_substantive_fragments_retained": not missing_fragments,
        "map_modes_identical": sorted(original_modes) == sorted(new_modes),
        "map_layers_identical": sorted(original_layers) == sorted(new_layers),
        "details_count_identical": original.details_count == reorganized.details_count,
        "tables_count_identical": original.tables_count == reorganized.tables_count,
        "no_duplicate_ids": len(ids) == len(set(ids)),
        "all_internal_links_resolve": not missing_targets,
        "required_section_order": all(positions[key] >= 0 for key in required_order)
        and list(positions.values()) == sorted(positions.values()),
    }
    result = {
        "checks": checks,
        "original_substantive_fragments": len(original_fragments),
        "missing_fragments": missing_fragments,
        "map_modes": new_modes,
        "map_layers": new_layers,
        "section_positions": positions,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
