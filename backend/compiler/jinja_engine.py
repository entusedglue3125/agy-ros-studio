#!/usr/bin/env python3
"""
Jinja2 Compiler Engine for Antigravity ROS Studio.
Compiles normalized AST JSON graphs into buildable standard ROS 2 ament Python packages.
"""

import os
import sys
import json
import textwrap
from typing import Dict, Any, List
import jinja2

TEMPLATES_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "templates")
)


class JinjaCompilerEngine:
    def __init__(self, templates_dir: str = TEMPLATES_DIR):
        self.templates_dir = templates_dir
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(self.templates_dir),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True
        )

    def compile_workspace(self, ast_data: Dict[str, Any], output_root: str) -> Dict[str, Any]:
        """
        Compiles the AST into a complete ROS 2 ament_python workspace package.

        Returns:
            Dict containing package metadata and list of generated files.
        """
        meta = ast_data.get("workspace_meta", {})
        pkg_name = meta.get("package_name", "my_robot_bringup")
        robot_model = ast_data.get("robot_model", {})
        robot_name = robot_model.get("name", "my_robot")
        nodes = ast_data.get("nodes", [])

        pkg_root = os.path.join(output_root, pkg_name)

        # 1. Create directory structure
        dirs_to_create = [
            pkg_root,
            os.path.join(pkg_root, "resource"),
            os.path.join(pkg_root, pkg_name),
            os.path.join(pkg_root, "launch"),
            os.path.join(pkg_root, "urdf"),
            os.path.join(pkg_root, "config"),
            os.path.join(pkg_root, "worlds"),
        ]
        for d in dirs_to_create:
            os.makedirs(d, exist_ok=True)

        generated_files = []

        def write_file(rel_path: str, content: str):
            full_path = os.path.join(pkg_root, rel_path)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            generated_files.append({
                "path": full_path,
                "relative_path": rel_path,
                "size_bytes": len(content.encode("utf-8"))
            })

        # 2. Render package.xml
        pkg_xml_tmpl = self.env.get_template("package.xml.jinja2")
        write_file("package.xml", pkg_xml_tmpl.render(ast_data))

        # 3. Render setup.py & setup.cfg
        setup_py_tmpl = self.env.get_template("setup.py.jinja2")
        write_file("setup.py", setup_py_tmpl.render(ast_data))

        setup_cfg_content = (
            "[develop]\n"
            "script_dir=$base/lib/" + pkg_name + "\n"
            "[install]\n"
            "install_scripts=$base/lib/" + pkg_name + "\n"
        )
        write_file("setup.cfg", setup_cfg_content)

        # 4. Create resource marker file
        write_file(os.path.join("resource", pkg_name), "")

        # 5. Create Python module __init__.py
        write_file(os.path.join(pkg_name, "__init__.py"), "# Generated package module\n")

        # 6. Render URDF / Xacro
        urdf_tmpl = self.env.get_template("robot.urdf.xacro.jinja2")
        write_file(os.path.join("urdf", f"{robot_name}.urdf.xacro"), urdf_tmpl.render(ast_data))

        # 7. Render Launch Script
        launch_tmpl = self.env.get_template("robot_bringup.launch.py.jinja2")
        write_file(os.path.join("launch", "robot_bringup.launch.py"), launch_tmpl.render(ast_data))

        # 8. Render ros_gz_bridge.yaml & Gazebo World
        if meta.get("hardware_target") == "gazebo_sim":
            bridge_tmpl = self.env.get_template("ros_gz_bridge.yaml.jinja2")
            write_file(os.path.join("config", "ros_gz_bridge.yaml"), bridge_tmpl.render(ast_data))

            world_tmpl = self.env.get_template("default.sdf.jinja2")
            write_file(os.path.join("worlds", "default.sdf"), world_tmpl.render(ast_data))

        # 9. Render custom Python node scripts
        custom_node_tmpl = self.env.get_template("custom_node.py.jinja2")
        for node in nodes:
            if node.get("package") == pkg_name and node.get("custom_code"):
                exec_name = node.get("executable", f"{node['name']}_node")
                class_name = "".join(part.capitalize() for part in node["name"].split("_")) + "Node"
                raw_code = node.get("custom_code", "")
                dedented = textwrap.dedent(raw_code).splitlines()
                formatted_code = "\n".join("    " + line if line.strip() else "" for line in dedented) + "\n"
                py_code = custom_node_tmpl.render(
                    node=node,
                    class_name=class_name,
                    custom_code=formatted_code
                )
                write_file(os.path.join(pkg_name, f"{exec_name}.py"), py_code)

        # 10. Generate Nav2 Parameters YAML if Nav2 or SLAM nodes present
        has_nav2 = any("nav2" in n.get("block_type", "").lower() or "slam" in n.get("block_type", "").lower() for n in nodes)
        if has_nav2:
            nav2_yaml = (
                "amcl:\n"
                "  ros__parameters:\n"
                "    use_sim_time: True\n"
                "    alpha1: 0.2\n"
                "    alpha2: 0.2\n"
                "    alpha3: 0.2\n"
                "    alpha4: 0.2\n"
                "    base_frame_id: 'base_footprint'\n"
                "    global_frame_id: 'map'\n"
                "    odom_frame_id: 'odom'\n"
                "    scan_topic: '/scan'\n"
                "\n"
                "bt_navigator:\n"
                "  ros__parameters:\n"
                "    use_sim_time: True\n"
                "    global_frame: 'map'\n"
                "    robot_base_frame: 'base_footprint'\n"
                "    odom_topic: '/odom'\n"
            )
            write_file(os.path.join("config", "nav2_params.yaml"), nav2_yaml)

        return {
            "package_name": pkg_name,
            "package_root": pkg_root,
            "file_count": len(generated_files),
            "files": generated_files
        }


def compile_ast_file(ast_file_path: str, output_root: str) -> Dict[str, Any]:
    with open(ast_file_path, "r", encoding="utf-8") as f:
        ast_data = json.load(f)
    engine = JinjaCompilerEngine()
    return engine.compile_workspace(ast_data, output_root)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 jinja_engine.py <path_to_ast.json> <output_dir>")
        sys.exit(1)

    ast_path = sys.argv[1]
    out_dir = sys.argv[2]
    result = compile_ast_file(ast_path, out_dir)
    print(f"✓ Compilation complete for '{result['package_name']}'!")
    print(f"  Root: {result['package_root']}")
    print(f"  Generated {result['file_count']} files:")
    for f in result["files"]:
        print(f"   • {f['relative_path']} ({f['size_bytes']} bytes)")
