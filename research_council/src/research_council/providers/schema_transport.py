"""Anthropic wire adaptation. Original Pydantic contracts remain the final validator.

Typed dictionaries use reversible key/value arrays, never additionalProperties:false on
an open dictionary. Unsupported bounds become instructions, not weaker domain validation.
Schemas beyond documented grammar limits are blocked before any request/reservation.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any


class SchemaCompatibilityError(ValueError):
    pass


UNSUPPORTED = {
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "minLength",
    "maxLength",
    "maxItems",
    "uniqueItems",
    "minProperties",
    "maxProperties",
    "propertyNames",
    "pattern",
}
FORMATS = {
    "date-time",
    "time",
    "date",
    "duration",
    "email",
    "hostname",
    "uri",
    "ipv4",
    "ipv6",
    "uuid",
}


def count_features(schema: dict[str, Any]) -> tuple[int, int]:
    optional = unions = 0

    def walk(node: Any) -> None:
        nonlocal optional, unions
        if not isinstance(node, dict):
            return
        optional += len(set(node.get("properties", {})) - set(node.get("required", [])))
        unions += int("anyOf" in node or isinstance(node.get("type"), list))
        for key in ("$defs", "definitions", "properties"):
            for child in node.get(key, {}).values():
                walk(child)
        for key in ("anyOf", "allOf", "oneOf"):
            for child in node.get(key, []):
                walk(child)
        for key in ("items", "additionalProperties"):
            walk(node.get(key))

    walk(schema)
    return optional, unions


@dataclass
class AnthropicSchema:
    canonical: dict[str, Any]
    wire: dict[str, Any]
    transformed: bool
    has_maps: bool

    def convert(self, value: Any, *, encode: bool = False) -> Any:
        defs = self.canonical.get("$defs", {})

        def visit(node: dict[str, Any], item: Any) -> Any:
            if "$ref" in node:
                return visit(defs[node["$ref"].rsplit("/", 1)[-1]], item)
            if "anyOf" in node:
                if item is None:
                    return None
                branches = [b for b in node["anyOf"] if b.get("type") != "null"]
                if len(branches) == 1:
                    return visit(branches[0], item)
                for branch in branches:
                    kind = branch.get("type")
                    if (
                        (kind == "string" and isinstance(item, str))
                        or (
                            kind in {"integer", "number"}
                            and isinstance(item, (int, float))
                            and not isinstance(item, bool)
                        )
                        or (kind == "boolean" and isinstance(item, bool))
                    ):
                        return visit(branch, item)
                raise ValueError("Unsupported union value")
            if node.get("type") == "array":
                if not isinstance(item, list):
                    raise ValueError("Expected transport array")
                return [visit(node["items"], child) for child in item]
            if node.get("type") == "object":
                extra = node.get("additionalProperties", False)
                if isinstance(extra, dict):
                    if encode:
                        if not isinstance(item, dict):
                            raise ValueError("Expected canonical map")
                        return [{"key": str(k), "value": visit(extra, v)} for k, v in item.items()]
                    if not isinstance(item, list):
                        raise ValueError("Expected key/value transport array")
                    result = {}
                    for row in item:
                        if (
                            not isinstance(row, dict)
                            or set(row) != {"key", "value"}
                            or not isinstance(row["key"], str)
                            or row["key"] in result
                        ):
                            raise ValueError("Malformed or duplicate transport map entry")
                        result[row["key"]] = visit(extra, row["value"])
                    return result
                if not isinstance(item, dict):
                    raise ValueError("Expected transport object")
                properties = node.get("properties", {})
                return {
                    key: visit(properties[key], child) if key in properties else child
                    for key, child in item.items()
                }
            return item

        return visit(self.canonical, value)


def anthropic_schema(schema: dict[str, Any]) -> AnthropicSchema:
    optional, unions = count_features(schema)
    if unions > 16:
        raise SchemaCompatibilityError(f"BLOCKED_UNION_LIMIT:{unions}>16")
    defs = schema.get("$defs", {})
    has_maps = False
    visiting: set[str] = set()

    def check_refs(node: Any) -> None:
        if isinstance(node, list):
            for child in node:
                check_refs(child)
        elif isinstance(node, dict):
            if "$ref" in node:
                ref = node["$ref"]
                if not ref.startswith("#/$defs/") or ref.rsplit("/", 1)[-1] not in defs:
                    raise SchemaCompatibilityError("BLOCKED_EXTERNAL_REFERENCE")
                if ref in visiting:
                    raise SchemaCompatibilityError("BLOCKED_RECURSIVE_SCHEMA")
                visiting.add(ref)
                check_refs(defs[ref.rsplit("/", 1)[-1]])
                visiting.remove(ref)
            for key, child in node.items():
                if key not in {"$defs", "default", "enum", "examples"}:
                    check_refs(child)

    check_refs(schema)

    def transform(node: dict[str, Any]) -> dict[str, Any]:
        nonlocal has_maps
        result = copy.deepcopy(node)
        constraints = {
            key: result.pop(key)
            for key in list(result)
            if key in UNSUPPORTED
            or (key == "minItems" and result[key] > 1)
            or (key == "format" and result[key] not in FORMATS)
        }
        if constraints:
            result["description"] = (
                result.get("description", "")
                + " Canonical validation constraints: "
                + json.dumps(constraints, sort_keys=True)
            ).strip()
        for key in ("$defs", "definitions", "properties"):
            if key in result:
                result[key] = {name: transform(child) for name, child in result[key].items()}
        for key in ("anyOf", "allOf"):
            if key in result:
                result[key] = [transform(child) for child in result[key]]
        if "oneOf" in result:
            raise SchemaCompatibilityError("BLOCKED_ONE_OF")
        if "items" in result:
            result["items"] = transform(result["items"])
        if result.get("type") == "object":
            extra = result.get("additionalProperties", False)
            if isinstance(extra, dict):
                if result.get("properties"):
                    raise SchemaCompatibilityError("BLOCKED_MIXED_OBJECT_MAP")
                has_maps = True
                result = {
                    key: value
                    for key, value in result.items()
                    if key
                    not in {"type", "additionalProperties", "required", "properties", "default"}
                } | {
                    "type": "array",
                    "description": result.get("description", "")
                    + " Dictionary encoded as unique key/value entries; empty dictionary is [].",
                    "items": {
                        "type": "object",
                        "properties": {"key": {"type": "string"}, "value": transform(extra)},
                        "required": ["key", "value"],
                        "additionalProperties": False,
                    },
                }
            elif extra is True:
                raise SchemaCompatibilityError("BLOCKED_UNTYPED_MAP")
            else:
                result["additionalProperties"] = False
                if optional > 24:
                    result["required"] = list(result.get("properties", {}))
        return result

    wire = transform(schema)
    if len(json.dumps(wire)) > 100_000:
        raise SchemaCompatibilityError("BLOCKED_GRAMMAR_SIZE_GUARD")
    return AnthropicSchema(schema, wire, wire != schema, has_maps)


TRANSPORT_INSTRUCTION = "\nReturn the requested wire schema. Dictionaries are arrays of unique {key,value} entries; use [] for empty dictionaries. Obey canonical constraints in field descriptions. Do not include hidden reasoning."
