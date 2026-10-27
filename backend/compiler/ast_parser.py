#!/usr/bin/env python3
"""
AST Parser & Normalizer for Antigravity ROS Studio.
Validates workspace JSON AST against schema and auto-calculates rigid-body inertial tensors.
"""

import json
import os
import sys
from typing import Dict, Any, Tuple
import jsonschema

DEFAULT_SCHEMA_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "schema", "workspace_ast.json")
)


def calculate_inertial_tensor(geometry: str, dimensions: list, mass: float) -> Dict[str, float]:
    """
    Auto-calculates rigid-body principal moments of inertia (Ixx, Iyy, Izz).
    """
    m = max(float(mass), 0.001)

    if geometry == "cylinder" and len(dimensions) >= 2:
        r = float(dimensions[0])
        h = float(dimensions[1])
        izz = 0.5 * m * (r ** 2)
        ixx = iyy = (1.0 / 12.0) * m * (3 * (r ** 2) + (h ** 2))
        return {
            "mass": round(m, 4),
            "ixx": round(max(ixx, 1e-5), 6),
            "iyy": round(max(iyy, 1e-5), 6),
            "izz": round(max(izz, 1e-5), 6),
        }
    elif geometry == "box" and len(dimensions) >= 3:
        d, w, h = float(dimensions[0]), float(dimensions[1]), float(dimensions[2])
        ixx = (1.0 / 12.0) * m * (w ** 2 + h ** 2)
        iyy = (1.0 / 12.0) * m * (d ** 2 + h ** 2)
        izz = (1.0 / 12.0) * m * (d ** 2 + w ** 2)
        return {
            "mass": round(m, 4),
            "ixx": round(max(ixx, 1e-5), 6),
            "iyy": round(max(iyy, 1e-5), 6),
            "izz": round(max(izz, 1e-5), 6),
        }
    elif geometry == "sphere" and len(dimensions) >= 1:
        r = float(dimensions[0])
        i = (2.0 / 5.0) * m * (r ** 2)
        return {
            "mass": round(m, 4),
            "ixx": round(max(i, 1e-5), 6),
            "iyy": round(max(i, 1e-5), 6),
            "izz": round(max(i, 1e-5), 6),
        }
    else:
        # Fallback default inertia tensor
        return {
            "mass": round(m, 4),
            "ixx": 0.01,
            "iyy": 0.01,
            "izz": 0.01,
        }


def parse_and_validate_ast(
    ast_data: Dict[str, Any], schema_path: str = DEFAULT_SCHEMA_PATH
) -> Tuple[bool, Dict[str, Any], list]:
    """
    Validates AST JSON data against the formal JSON Schema and normalizes links,
    auto-calculating missing inertial moments.

    Returns:
        (is_valid, normalized_ast, list_of_errors)
    """
    errors = []

    # 1. Load schema
    if not os.path.exists(schema_path):
        return False, ast_data, [f"Schema file not found at: {schema_path}"]

    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
    except Exception as e:
        return False, ast_data, [f"Failed to read schema JSON: {e}"]

    # 2. Schema validation
    try:
        jsonschema.validate(instance=ast_data, schema=schema)
    except jsonschema.exceptions.ValidationError as e:
        errors.append(f"JSON Schema Validation Error at {list(e.path)}: {e.message}")
        return False, ast_data, errors

    # 3. Normalization & Inertia Auto-Calculation
    normalized_ast = json.loads(json.dumps(ast_data))  # Deep copy
    robot_model = normalized_ast.get("robot_model", {})
    links = robot_model.get("links", [])

    for link in links:
        vis = link.get("visual", {})
        col = link.get("collision", {})
        geometry = vis.get("geometry") or col.get("geometry") or "box"
        dimensions = vis.get("dimensions") or col.get("dimensions") or [0.1, 0.1, 0.1]

        inertial = link.get("inertial", {})
        mass = inertial.get("mass", 1.0)

        # Check if ixx, iyy, izz need calculation
        needs_calculation = (
            "ixx" not in inertial
            or "iyy" not in inertial
            or "izz" not in inertial
            or inertial.get("ixx", 0) <= 0
        )

        if needs_calculation:
            calc_inertial = calculate_inertial_tensor(geometry, dimensions, mass)
            link["inertial"] = calc_inertial

    return True, normalized_ast, []


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 ast_parser.py <path_to_ast.json>")
        sys.exit(1)

    file_path = sys.argv[1]
    with open(file_path, "r", encoding="utf-8") as fp:
        raw_ast = json.load(fp)

    valid, norm_ast, errs = parse_and_validate_ast(raw_ast)
    if valid:
        print(f"✓ AST is valid! Normalized {len(norm_ast['robot_model']['links'])} links.")
    else:
        print("✗ AST Validation Failed:")
        for err in errs:
            print(f"  - {err}")
        sys.exit(1)
