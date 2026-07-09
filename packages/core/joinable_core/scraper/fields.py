from __future__ import annotations

from bs4 import Tag

from joinable_core.schemas import CombineFieldSpec, FieldSpec
from joinable_core.scraper.normalize import extract_attr, extract_text

FieldValue = str | FieldSpec | CombineFieldSpec


def _element_text(element: Tag, attribute: str | None) -> str | None:
    if attribute:
        raw = element.get(attribute)
        if isinstance(raw, str):
            return raw.strip() or None
        return None
    text = " ".join(element.get_text(separator=" ", strip=True).split())
    return text or None


def _matches_filter(element: Tag, match: str | None) -> bool:
    if not match:
        return True
    text = element.get_text(separator=" ", strip=True)
    return match in text


def find_preceding(container: Tag, selector: str, match: str | None = None) -> Tag | None:
    for element in container.find_all_previous(selector):
        if _matches_filter(element, match):
            return element
    return None


def find_ancestor_match(container: Tag, selector: str, match: str | None = None) -> Tag | None:
    for parent in container.parents:
        if not isinstance(parent, Tag):
            continue
        if parent.name in {"html", "[document]"}:
            break
        found = parent.select_one(selector)
        if found is not None and _matches_filter(found, match):
            return found
    return None


def extract_from_spec(container: Tag, spec: FieldSpec) -> str | None:
    if spec.scope == "container":
        if spec.attribute:
            return extract_attr(container, spec.selector, spec.attribute)
        return extract_text(container, spec.selector)

    target: Tag | None
    if spec.scope == "preceding":
        target = find_preceding(container, spec.selector, spec.match)
    else:
        target = find_ancestor_match(container, spec.selector, spec.match)

    if target is None:
        return None
    return _element_text(target, spec.attribute)


def extract_field(
    container: Tag,
    value: FieldValue | None,
    *,
    legacy_attribute: str | None = None,
) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        if legacy_attribute:
            return extract_attr(container, value, legacy_attribute)
        return extract_text(container, value)
    if isinstance(value, FieldSpec):
        return extract_from_spec(container, value)
    if isinstance(value, CombineFieldSpec):
        rendered: dict[str, str] = {}
        for key, part in value.parts.items():
            part_value = extract_from_spec(container, part)
            if not part_value:
                return None
            rendered[key] = part_value
        try:
            return value.template.format(**rendered).strip()
        except KeyError:
            return None
    return None
