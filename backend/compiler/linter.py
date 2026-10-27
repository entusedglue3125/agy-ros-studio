#!/usr/bin/env python3
"""
Pre-Flight Static Graph Linter for Antigravity ROS Studio.
Enforces 4 critical pre-flight checks:
1. Acyclic TF2 frame graph continuity and connectivity.
2. DDS Port QoS compatibility (Reliability & Durability contracts).
3. Topic and message interface typing across connected wires.
4. Python AST syntax validation for custom node code stubs.
"""

import ast
import textwrap
from typing import Dict, Any, List, Tuple


class PreFlightLinter:
    def __init__(self, workspace_ast: Dict[str, Any]):
        self.ast = workspace_ast
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def run_all_checks(self) -> Tuple[bool, List[str], List[str]]:
        """
        Executes all 4 static checks.
        Returns: (passed, errors, warnings)
        """
        self.errors.clear()
        self.warnings.clear()

        self.check_1_tf2_continuity()
        self.check_2_qos_compatibility()
        self.check_3_wire_typing()
        self.check_4_custom_code_syntax()

        passed = len(self.errors) == 0
        return passed, self.errors, self.warnings

    def check_1_tf2_continuity(self):
        """
        Check 1: Acyclic TF2 frame continuity.
        Inspects robot joints and node TF broadcasts (e.g., slam_toolbox, diff_drive).
        Verifies there are no directed cycles and all sensor frames link back to base_link.
        """
        robot = self.ast.get("robot_model", {})
        joints = robot.get("joints", [])
        base_link = robot.get("base_link", "base_link")

        # Build adjacency graph for TF frames
        # Edge: parent -> child
        adj: Dict[str, List[str]] = {}
        all_frames = set()

        # Built-in base_footprint -> base_link
        adj.setdefault("base_footprint", []).append(base_link)
        all_frames.add("base_footprint")
        all_frames.add(base_link)

        for joint in joints:
            p = joint.get("parent")
            c = joint.get("child")
            if p and c:
                adj.setdefault(p, []).append(c)
                all_frames.add(p)
                all_frames.add(c)

        # Also inspect nodes for external TF broadcasters (e.g., SLAM map->odom, diff_drive odom->base_footprint)
        for node in self.ast.get("nodes", []):
            btype = node.get("block_type", "")
            if "slam" in btype.lower():
                adj.setdefault("map", []).append("odom")
                all_frames.add("map")
                all_frames.add("odom")
            if "gazebo" in btype.lower() or "chassis" in btype.lower() or "odom" in btype.lower() or "diff" in btype.lower():
                adj.setdefault("odom", []).append("base_footprint")
                all_frames.add("odom")
                all_frames.add("base_footprint")

        # Cycle detection using DFS
        visited = {}  # 0 = unvisited, 1 = visiting (in stack), 2 = visited

        def has_cycle(u: str) -> bool:
            visited[u] = 1
            for v in adj.get(u, []):
                if visited.get(v, 0) == 1:
                    self.errors.append(f"TF2 Cycle detected between frame '{u}' and '{v}'!")
                    return True
                elif visited.get(v, 0) == 0:
                    if has_cycle(v):
                        return True
            visited[u] = 2
            return False

        for frame in list(all_frames):
            if visited.get(frame, 0) == 0:
                has_cycle(frame)

        # Check reachability from base_link to sensor frames
        reachable_from_base = set()

        def dfs_reach(u: str):
            reachable_from_base.add(u)
            for v in adj.get(u, []):
                if v not in reachable_from_base:
                    dfs_reach(v)

        dfs_reach(base_link)

        # Identify sensor joints/links that should be connected
        for joint in joints:
            child = joint.get("child", "")
            if any(term in child.lower() for term in ["laser", "lidar", "imu", "camera", "sonar"]):
                if child not in reachable_from_base:
                    self.warnings.append(
                        f"Sensor frame '{child}' is not reachable from base_link '{base_link}' in TF graph!"
                    )

    def check_2_qos_compatibility(self):
        """
        Check 2: Port QoS compatibility.
        DDS Rule: Subscriber cannot request stronger QoS than Publisher offers.
        - Publisher BEST_EFFORT + Subscriber RELIABLE => Incompatible!
        - Publisher VOLATILE + Subscriber TRANSIENT_LOCAL => Incompatible!
        """
        nodes_by_id = {n["id"]: n for n in self.ast.get("nodes", [])}
        wires = self.ast.get("wires", [])

        for wire in wires:
            from_node = nodes_by_id.get(wire.get("from_node"))
            to_node = nodes_by_id.get(wire.get("to_node"))

            if not from_node or not to_node:
                continue

            # Find ports
            from_port = next((p for p in from_node.get("ports", []) if p["id"] == wire.get("from_port")), None)
            to_port = next((p for p in to_node.get("ports", []) if p["id"] == wire.get("to_port")), None)

            if not from_port or not to_port:
                continue

            pub_qos = from_port.get("qos", {})
            sub_qos = to_port.get("qos", {})

            pub_rel = pub_qos.get("reliability", "reliable").lower()
            sub_rel = sub_qos.get("reliability", "reliable").lower()

            if pub_rel == "best_effort" and sub_rel == "reliable":
                self.errors.append(
                    f"QoS Incompatibility on wire '{wire.get('id')}': "
                    f"Publisher '{from_node.get('name')}.{from_port.get('name')}' offers BEST_EFFORT, "
                    f"but Subscriber '{to_node.get('name')}.{to_port.get('name')}' requests RELIABLE. "
                    f"DDS will silently drop packets!"
                )

            pub_dur = pub_qos.get("durability", "volatile").lower()
            sub_dur = sub_qos.get("durability", "volatile").lower()

            if pub_dur == "volatile" and sub_dur == "transient_local":
                self.warnings.append(
                    f"QoS Durability Warning on wire '{wire.get('id')}': "
                    f"Publisher '{from_node.get('name')}' offers VOLATILE, "
                    f"but Subscriber '{to_node.get('name')}' requests TRANSIENT_LOCAL."
                )

    def check_3_wire_typing(self):
        """
        Check 3: Topic and message interface typing across connected wires.
        Verifies that publisher and subscriber port msg_types match exactly.
        """
        nodes_by_id = {n["id"]: n for n in self.ast.get("nodes", [])}
        wires = self.ast.get("wires", [])

        for wire in wires:
            from_node = nodes_by_id.get(wire.get("from_node"))
            to_node = nodes_by_id.get(wire.get("to_node"))

            if not from_node or not to_node:
                self.errors.append(f"Wire '{wire.get('id')}' references non-existent node ID.")
                continue

            from_port = next((p for p in from_node.get("ports", []) if p["id"] == wire.get("from_port")), None)
            to_port = next((p for p in to_node.get("ports", []) if p["id"] == wire.get("to_port")), None)

            if not from_port or not to_port:
                self.errors.append(f"Wire '{wire.get('id')}' references non-existent port ID.")
                continue

            # Verify direction
            if from_port.get("direction") != "output" or to_port.get("direction") != "input":
                self.errors.append(
                    f"Wire '{wire.get('id')}' connects invalid port directions: "
                    f"{from_port.get('direction')} -> {to_port.get('direction')} (must be output -> input)."
                )

            # Verify msg_type
            pub_type = from_port.get("msg_type", "").strip()
            sub_type = to_port.get("msg_type", "").strip()

            if pub_type and sub_type and pub_type != sub_type:
                self.errors.append(
                    f"Type Mismatch on wire '{wire.get('id')}': "
                    f"Publisher '{from_node.get('name')}' emits '{pub_type}', "
                    f"but Subscriber '{to_node.get('name')}' expects '{sub_type}'."
                )

    def check_4_custom_code_syntax(self):
        """
        Check 4: Python ast.parse() syntax validation for custom node blocks.
        """
        for node in self.ast.get("nodes", []):
            code = node.get("custom_code")
            if code and code.strip():
                try:
                    ast.parse(textwrap.dedent(code))
                except SyntaxError as e:
                    self.errors.append(
                        f"Python SyntaxError in custom code for node '{node.get('name')}' "
                        f"(line {e.lineno}, col {e.offset}): {e.msg}"
                    )


def lint_ast(workspace_ast: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
    """Convenience helper function."""
    linter = PreFlightLinter(workspace_ast)
    return linter.run_all_checks()


if __name__ == "__main__":
    import json, sys
    if len(sys.argv) < 2:
        print("Usage: python3 linter.py <path_to_ast.json>")
        sys.exit(1)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        data = json.load(f)

    ok, errs, warns = lint_ast(data)
    print(f"Linter Result: {'PASSED' if ok else 'FAILED'}")
    if errs:
        print("Errors:")
        for e in errs:
            print(f"  ✗ {e}")
    if warns:
        print("Warnings:")
        for w in warns:
            print(f"  ⚠ {w}")
    sys.exit(0 if ok else 1)
