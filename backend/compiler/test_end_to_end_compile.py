#!/usr/bin/env python3
"""
End-to-End Compiler & Architecture Verification Test Suite.
Validates:
1. AST schema validation & inertia tensor auto-calculation (ast_parser.py).
2. Static Graph Linter checks (TF2 acyclic, QoS, Wire typing, Python AST) (linter.py).
3. Jinja2 compilation into buildable ROS 2 ament package (jinja_engine.py).
4. Vendor modules functionality (qos_resolver, stream_session, doctor_parser, process_manager).
"""

import os
import sys
import json
import ast

# Ensure backend modules are on PYTHONPATH
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, BASE_DIR)

from backend.compiler.ast_parser import parse_and_validate_ast
from backend.compiler.linter import lint_ast
from backend.compiler.jinja_engine import JinjaCompilerEngine
from backend.vendors.wise_vision.stream_session import StreamSession
from backend.vendors.wise_vision.qos_resolver import QoSResolver
from backend.vendors.rde_ros2.doctor_parser import DoctorParser
from backend.runtime.process_manager import ProcessManager


def run_e2e_test():
    print("=====================================================================")
    print("🧪 RUNNING ANTIGRAVITY ROS STUDIO END-TO-END VERIFICATION SUITE")
    print("=====================================================================")

    sample_ast_path = os.path.join(BASE_DIR, "schema", "sample_rover_ast.json")
    output_dir = os.path.join(BASE_DIR, "build_output")

    # TEST 1: Load and parse AST
    print("\n[TEST 1] Loading sample AST and running ast_parser...")
    with open(sample_ast_path, "r", encoding="utf-8") as f:
        raw_ast = json.load(f)

    is_valid, normalized_ast, errs = parse_and_validate_ast(raw_ast)
    assert is_valid, f"AST Validation failed: {errs}"
    print(f"✓ AST is valid against JSON schema.")
    
    # Check that inertia was auto-calculated
    base_link = next(l for l in normalized_ast["robot_model"]["links"] if l["name"] == "base_link")
    assert "ixx" in base_link["inertial"], "Inertial tensor missing from base_link!"
    print(f"✓ Base link inertia auto-calculated: {base_link['inertial']}")

    left_wheel = next(l for l in normalized_ast["robot_model"]["links"] if l["name"] == "left_wheel")
    assert "izz" in left_wheel["inertial"], "Inertial tensor missing from left_wheel!"
    print(f"✓ Wheel cylinder inertia auto-calculated: {left_wheel['inertial']}")

    # TEST 2: Run Static Graph Linter
    print("\n[TEST 2] Running Pre-Flight Static Graph Linter...")
    linter_passed, linter_errors, linter_warnings = lint_ast(normalized_ast)
    if linter_warnings:
        print(f"⚠ Linter Warnings: {linter_warnings}")
    assert linter_passed, f"Linter checks failed with errors: {linter_errors}"
    print("✓ Pre-Flight Static Graph Linter PASSED with 0 errors!")
    print("   • TF2 Frame Graph is strictly acyclic and continuous.")
    print("   • QoS Reliability and Durability contracts are 100% matched.")
    print("   • Wire port directions and message types match.")
    print("   • Custom Python node callbacks parsed cleanly via ast.parse().")

    # TEST 3: Jinja2 Package Compilation
    print("\n[TEST 3] Running Jinja2 Compiler Engine...")
    engine = JinjaCompilerEngine()
    compile_result = engine.compile_workspace(normalized_ast, output_dir)
    pkg_root = compile_result["package_root"]
    file_count = compile_result["file_count"]

    print(f"✓ Compilation successful! Generated {file_count} files at: {pkg_root}")

    # Verify critical generated files
    expected_files = [
        "package.xml",
        "setup.py",
        "setup.cfg",
        os.path.join("launch", "robot_bringup.launch.py"),
        os.path.join("urdf", "agy_rover.urdf.xacro"),
        os.path.join("config", "ros_gz_bridge.yaml"),
        os.path.join("config", "nav2_params.yaml"),
        os.path.join("worlds", "default.sdf"),
        os.path.join("agy_rover_bringup", "safety_filter.py"),
    ]

    for rel in expected_files:
        full_p = os.path.join(pkg_root, rel)
        assert os.path.exists(full_p), f"Missing expected generated file: {full_p}"
        size = os.path.getsize(full_p)
        assert size > 0, f"Generated file is empty: {full_p}"
        print(f"   ✓ Verified: {rel} ({size} bytes)")

    # TEST 4: Syntax validate generated Python scripts
    print("\n[TEST 4] Validating syntax of generated Python files...")
    launch_file = os.path.join(pkg_root, "launch", "robot_bringup.launch.py")
    with open(launch_file, "r", encoding="utf-8") as f:
        launch_code = f.read()
    ast.parse(launch_code)
    print("✓ Generated 'robot_bringup.launch.py' is 100% valid Python syntax.")

    custom_node_file = os.path.join(pkg_root, "agy_rover_bringup", "safety_filter.py")
    with open(custom_node_file, "r", encoding="utf-8") as f:
        node_code = f.read()
    ast.parse(node_code)
    print("✓ Generated 'safety_filter.py' is 100% valid Python syntax.")

    # TEST 5: Verify Vendor Modules
    print("\n[TEST 5] Testing Extracted Vendor Modules...")
    
    # 5.1 StreamSession
    sess = StreamSession("sess_001", "/scan", "sensor_msgs/msg/LaserScan")
    for _ in range(5):
        sess.on_message_received(None)
    telemetry = sess.get_telemetry_snapshot()
    assert telemetry["rx_count"] == 5, "StreamSession message count mismatch!"
    print(f"✓ StreamSession telemetry verified: rx_count={telemetry['rx_count']}, topic={telemetry['topic_name']}")

    # 5.2 QoSResolver
    mock_profile = QoSResolver.get_qos_profile_for_topic(None, "/scan")
    assert "reliability" in mock_profile, "QoS profile resolver failed!"
    print(f"✓ QoSResolver verified.")

    # 5.3 DoctorParser
    sample_doc = "[ERROR] ROS_DISTRO: not set\n[OK] network: multicast enabled\n"
    parsed_doc = DoctorParser.parse_doctor_output(sample_doc, returncode=1)
    assert parsed_doc["overall_status"] == "error", "DoctorParser error detection failed!"
    assert parsed_doc["check_count"] == 2, "DoctorParser check count mismatch!"
    print(f"✓ DoctorParser verified: {parsed_doc['check_count']} checks parsed, overall status: {parsed_doc['overall_status']}")

    # 5.4 ProcessManager
    pm = ProcessManager()
    launch_res = pm.launch_process("test_daemon", ["sleep", "1"], process_type="test")
    assert launch_res["success"], "ProcessManager failed to launch process!"
    term_res = pm.terminate_process("test_daemon")
    assert term_res["success"], "ProcessManager failed to terminate process!"
    print(f"✓ ProcessManager verified: process launched with PID {launch_res['pid']}, PGID {launch_res['pgid']}, gracefully terminated.")

    print("\n=====================================================================")
    print("🎉 ALL 5 E2E TESTS PASSED PERFECTLY! PHASE 1 & VENDOR EXTRACTION COMPLETE!")
    print("=====================================================================")


if __name__ == "__main__":
    run_e2e_test()
