#!/usr/bin/env python3
"""Validate an output JSON artifact against a contract schema.

Usage:
  python3 validate_contract.py <output.json> <schema.json> [constraints.json]
  python3 validate_contract.py outputs/run-dir/output/walking_plan.json books/pmf-engine/contracts/walking_plan.json

If a constraints file is not passed explicitly, a sibling file named
"<schema-stem>.constraints.json" next to the schema is auto-loaded when present.

Exits 0 on success, 1 on validation failure.
"""
import json
import os
import sys

TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
}


def validate(data, schema, path=""):
    errors = []
    for key, expected in schema.items():
        full_path = f"{path}.{key}" if path else key
        if key not in data:
            errors.append(f"Missing: {full_path}")
            continue
        value = data[key]
        if isinstance(expected, str):
            checker = TYPE_CHECKS.get(expected)
            if checker and not checker(value):
                errors.append(
                    f"Wrong type for {full_path}: expected {expected}, "
                    f"got {type(value).__name__} (value: {repr(value)[:80]})"
                )
        elif isinstance(expected, dict):
            if not isinstance(value, dict):
                errors.append(
                    f"Wrong type for {full_path}: expected object, got {type(value).__name__}"
                )
            else:
                errors.extend(validate(value, expected, full_path))
        elif isinstance(expected, list) and len(expected) == 1:
            if not isinstance(value, list):
                errors.append(
                    f"Wrong type for {full_path}: expected array, got {type(value).__name__}"
                )
            elif len(value) == 0:
                errors.append(f"Empty array: {full_path}")
            else:
                item_schema = expected[0]
                for i, item in enumerate(value):
                    item_path = f"{full_path}[{i}]"
                    if isinstance(item_schema, dict):
                        if not isinstance(item, dict):
                            errors.append(
                                f"Wrong type for {item_path}: expected object, "
                                f"got {type(item).__name__}"
                            )
                        else:
                            errors.extend(validate(item, item_schema, item_path))
                    elif isinstance(item_schema, str):
                        checker = TYPE_CHECKS.get(item_schema)
                        if checker and not checker(item):
                            errors.append(
                                f"Wrong type for {item_path}: expected {item_schema}, "
                                f"got {type(item).__name__}"
                            )
    return errors


def resolve_path(data, path):
    """Walk a dotted path with optional `[]` array iteration.

    Returns a list of (concrete_path, value) tuples. Missing intermediate
    fields are silently skipped — caller decides whether missing = error.
    """
    results = []
    _walk(data, path.split("."), 0, "", results)
    return results


def _walk(current, segments, idx, concrete, out):
    if idx == len(segments):
        out.append((concrete, current))
        return
    segment = segments[idx]
    if segment.endswith("[]"):
        key = segment[:-2]
        if key:
            if not isinstance(current, dict) or key not in current:
                return
            current = current[key]
        if not isinstance(current, list):
            return
        base = f"{concrete}.{key}" if concrete and key else (key if not concrete else concrete)
        for i, item in enumerate(current):
            item_concrete = f"{base}[{i}]" if key or concrete else f"[{i}]"
            _walk(item, segments, idx + 1, item_concrete, out)
    else:
        if not isinstance(current, dict) or segment not in current:
            return
        next_concrete = f"{concrete}.{segment}" if concrete else segment
        _walk(current[segment], segments, idx + 1, next_concrete, out)


def _resolve_single(data, path):
    matches = resolve_path(data, path)
    if not matches:
        return None, False
    return matches[0][1], True


def validate_constraints(data, constraints):
    """Check enum, range, array_length, exact_ids, and equals constraints."""
    errors = []

    for rule in constraints.get("enums", []):
        path = rule["path"]
        allowed = set(rule["values"])
        matches = resolve_path(data, path)
        if not matches:
            errors.append(f"Enum path not found: {path}")
            continue
        for concrete, value in matches:
            if value not in allowed:
                errors.append(
                    f"Enum violation at {concrete}: got {value!r}, expected one of {sorted(allowed)}"
                )

    for rule in constraints.get("ranges", []):
        path = rule["path"]
        lo = rule.get("min")
        hi = rule.get("max")
        matches = resolve_path(data, path)
        if not matches:
            errors.append(f"Range path not found: {path}")
            continue
        for concrete, value in matches:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                errors.append(f"Range target at {concrete} is not numeric: {value!r}")
                continue
            if lo is not None and value < lo:
                errors.append(f"Range violation at {concrete}: {value} < min {lo}")
            if hi is not None and value > hi:
                errors.append(f"Range violation at {concrete}: {value} > max {hi}")

    for rule in constraints.get("array_length", []):
        path = rule["path"]
        matches = resolve_path(data, path)
        if not matches:
            errors.append(f"Array length path not found: {path}")
            continue
        for concrete, value in matches:
            if not isinstance(value, list):
                errors.append(f"Array length target at {concrete} is not a list: {type(value).__name__}")
                continue
            length = len(value)
            if "exact" in rule and length != rule["exact"]:
                errors.append(
                    f"Array length violation at {concrete}: got {length}, expected exactly {rule['exact']}"
                )
            if "min" in rule and length < rule["min"]:
                errors.append(
                    f"Array length violation at {concrete}: got {length}, expected min {rule['min']}"
                )
            if "max" in rule and length > rule["max"]:
                errors.append(
                    f"Array length violation at {concrete}: got {length}, expected max {rule['max']}"
                )

    for rule in constraints.get("exact_ids", []):
        path = rule["path"]
        expected = list(rule["values"])
        matches = resolve_path(data, path)
        if not matches:
            errors.append(f"Exact-ids path not found: {path}")
            continue
        actual = [v for _, v in matches]
        if sorted(actual) != sorted(expected):
            missing = sorted(set(expected) - set(actual))
            extra = sorted(set(actual) - set(expected))
            parts = []
            if missing:
                parts.append(f"missing {missing}")
            if extra:
                parts.append(f"unexpected {extra}")
            if len(actual) != len(expected):
                parts.append(f"got {len(actual)}, expected {len(expected)}")
            errors.append(f"Exact-ids violation at {path}: " + "; ".join(parts))

    for rule in constraints.get("equals", []):
        left_path = rule["left"]
        right = rule["right"]
        left_value, found = _resolve_single(data, left_path)
        if not found:
            errors.append(f"Equals left path not found: {left_path}")
            continue
        right_value = _evaluate_right(data, right, errors, left_path)
        if right_value is None:
            continue
        if left_value != right_value:
            errors.append(
                f"Equals violation at {left_path}: left={left_value}, right={right_value} "
                f"(right expression: {right})"
            )

    return errors


def _evaluate_right(data, right, errors, left_path):
    if isinstance(right, (int, float, str, bool)):
        return right
    if isinstance(right, dict):
        if "count" in right:
            path = right["count"]
            value, found = _resolve_single(data, path)
            if not found or not isinstance(value, list):
                errors.append(f"Equals right count path not a list: {path}")
                return None
            return len(value)
        if "sum" in right:
            path = right["sum"]
            matches = resolve_path(data, path)
            if not matches:
                errors.append(f"Equals right sum path not found: {path}")
                return None
            total = 0
            for concrete, value in matches:
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    errors.append(f"Equals right sum non-numeric at {concrete}: {value!r}")
                    return None
                total += value
            return total
    errors.append(f"Equals right expression not understood for {left_path}: {right!r}")
    return None


def _default_constraints_path(schema_path):
    base, ext = os.path.splitext(schema_path)
    candidate = f"{base}.constraints.json"
    return candidate if os.path.exists(candidate) else None


def main():
    if len(sys.argv) not in (3, 4):
        print(f"Usage: {sys.argv[0]} <output.json> <schema.json> [constraints.json]")
        sys.exit(2)

    output_path, schema_path = sys.argv[1], sys.argv[2]
    constraints_path = sys.argv[3] if len(sys.argv) == 4 else _default_constraints_path(schema_path)

    data = json.load(open(output_path))
    schema = json.load(open(schema_path))
    constraints = json.load(open(constraints_path)) if constraints_path else None

    errors = validate(data, schema)
    if constraints:
        errors.extend(validate_constraints(data, constraints))

    if errors:
        print(f"FAIL: {output_path}")
        for e in errors[:30]:
            print(f"  {e}")
        if len(errors) > 30:
            print(f"  ... and {len(errors) - 30} more errors")
        sys.exit(1)
    else:
        suffix = f" (+constraints: {os.path.basename(constraints_path)})" if constraints_path else ""
        print(f"PASS: {output_path}{suffix}")


if __name__ == "__main__":
    main()
