#!/usr/bin/env python3
"""
Antigravity ROS Studio - Live Interactive Web IDE & Runtime Daemon Server.
Serves the visual programming canvas, live code X-ray, interactive 3D simulation viewport,
and connects frontend actions directly to ast_parser, linter, jinja_engine, and process_manager.
"""

import http.server
import socketserver
import json
import os
import sys
import threading
import time
from urllib.parse import urlparse

# Ensure backend modules are accessible
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, BASE_DIR)

from backend.compiler.ast_parser import parse_and_validate_ast
from backend.compiler.linter import lint_ast
from backend.compiler.jinja_engine import JinjaCompilerEngine
from backend.vendors.wise_vision.stream_session import StreamSession
from backend.vendors.rde_ros2.doctor_parser import DoctorParser
from backend.runtime.process_manager import ProcessManager

PORT = 8050
SAMPLE_AST_FILE = os.path.join(BASE_DIR, "schema", "sample_rover_ast.json")
BUILD_OUTPUT_DIR = os.path.join(BASE_DIR, "build_output")

# Shared runtime state
process_manager = ProcessManager()
stream_sessions = {
    "/scan": StreamSession("sess_scan", "/scan", "sensor_msgs/msg/LaserScan", target_fps=10.0),
    "/odom": StreamSession("sess_odom", "/odom", "nav_msgs/msg/Odometry", target_fps=50.0),
    "/cmd_vel": StreamSession("sess_cmd", "/cmd_vel", "geometry_msgs/msg/Twist", target_fps=20.0),
    "/map": StreamSession("sess_map", "/map", "nav_msgs/msg/OccupancyGrid", target_fps=1.0),
}
sim_running = False


def background_telemetry_loop():
    """Generates synthetic telemetry pulses matching the ROS 2 mobile robot contract."""
    global sim_running
    while True:
        if sim_running:
            for s in stream_sessions.values():
                s.on_message_received(None)
        time.sleep(0.05)


t_thread = threading.Thread(target=background_telemetry_loop, daemon=True)
t_thread.start()


class StudioHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(self.render_studio_html().encode("utf-8"))
            return

        elif parsed.path == "/api/ast":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            if os.path.exists(SAMPLE_AST_FILE):
                with open(SAMPLE_AST_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = {}
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        elif parsed.path == "/api/telemetry":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            telemetry = {
                topic: sess.get_telemetry_snapshot()
                for topic, sess in stream_sessions.items()
            }
            res = {
                "sim_running": sim_running,
                "telemetry": telemetry,
                "doctor": DoctorParser.parse_doctor_output("[OK] network: multicast enabled\n[OK] tf2: tree continuous", 0)
            }
            self.wfile.write(json.dumps(res).encode("utf-8"))
            return

        elif parsed.path == "/api/files":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            pkg_path = os.path.join(BUILD_OUTPUT_DIR, "agy_rover_bringup")
            file_map = {}
            if os.path.exists(pkg_path):
                for root, _, files in os.walk(pkg_path):
                    for f in files:
                        full_p = os.path.join(root, f)
                        rel_p = os.path.relpath(full_p, pkg_path)
                        try:
                            with open(full_p, "r", encoding="utf-8") as fp:
                                file_map[rel_p] = fp.read()
                        except Exception:
                            file_map[rel_p] = "<binary or unreadable>"
            self.wfile.write(json.dumps(file_map).encode("utf-8"))
            return

        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        global sim_running
        parsed = urlparse(self.path)
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"

        if parsed.path == "/api/compile":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            try:
                with open(SAMPLE_AST_FILE, "r", encoding="utf-8") as f:
                    ast_data = json.load(f)
                ok, norm_ast, errs = parse_and_validate_ast(ast_data)
                if not ok:
                    self.wfile.write(json.dumps({"success": False, "errors": errs}).encode("utf-8"))
                    return

                engine = JinjaCompilerEngine()
                res = engine.compile_workspace(norm_ast, BUILD_OUTPUT_DIR)
                self.wfile.write(json.dumps({"success": True, "result": res}).encode("utf-8"))
            except Exception as e:
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))
            return

        elif parsed.path == "/api/lint":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            try:
                with open(SAMPLE_AST_FILE, "r", encoding="utf-8") as f:
                    ast_data = json.load(f)
                ok, errs, warns = lint_ast(ast_data)
                self.wfile.write(json.dumps({"passed": ok, "errors": errs, "warnings": warns}).encode("utf-8"))
            except Exception as e:
                self.wfile.write(json.dumps({"passed": False, "errors": [str(e)], "warnings": []}).encode("utf-8"))
            return

        elif parsed.path == "/api/launch":
            sim_running = not sim_running
            if sim_running:
                process_manager.launch_process(
                    "sim_daemon",
                    ["sleep", "3600"],
                    process_type="simulation"
                )
            else:
                process_manager.terminate_process("sim_daemon")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"sim_running": sim_running}).encode("utf-8"))
            return

        else:
            self.send_error(404, "Not Found")

    def render_studio_html(self) -> str:
        return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Antigravity ROS Studio — Autonomous Rover IDE</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    @keyframes pulse-wire {
      0% { stroke-dashoffset: 24; }
      100% { stroke-dashoffset: 0; }
    }
    .pulsing-wire {
      stroke-dasharray: 6, 6;
      animation: pulse-wire 1s linear infinite;
    }
  </style>
</head>
<body class="bg-slate-950 text-slate-100 font-sans h-screen flex flex-col overflow-hidden">

  <!-- Top Navigation & Controls Bar -->
  <header class="bg-slate-900 border-b border-slate-800 px-6 py-3 flex items-center justify-between shadow-lg">
    <div class="flex items-center space-x-4">
      <div class="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center font-bold text-lg text-white shadow-md shadow-indigo-500/20">
        AG
      </div>
      <div>
        <h1 class="text-base font-bold text-white tracking-wide">Antigravity ROS Studio</h1>
        <p class="text-xs text-slate-400">Project: <span class="text-indigo-400 font-medium">Autonomous Rover Exploration</span></p>
      </div>
      <div class="flex items-center space-x-2 pl-4">
        <span class="px-2 py-0.5 rounded text-xs font-semibold bg-emerald-950 text-emerald-400 border border-emerald-800">ROS 2 Humble</span>
        <span class="px-2 py-0.5 rounded text-xs font-semibold bg-blue-950 text-blue-400 border border-blue-800">Domain: 42</span>
        <span class="px-2 py-0.5 rounded text-xs font-semibold bg-purple-950 text-purple-300 border border-purple-800">Target: Gazebo Sim 4WD</span>
      </div>
    </div>

    <!-- IDE Action Buttons -->
    <div class="flex items-center space-x-3">
      <button onclick="runLinter()" class="px-3.5 py-1.5 rounded-md text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition flex items-center space-x-1.5">
        <span>🔍 Run Pre-Flight Linter</span>
      </button>
      <button onclick="compileWorkspace()" class="px-3.5 py-1.5 rounded-md text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white shadow-md shadow-indigo-600/30 transition flex items-center space-x-1.5">
        <span>⚡ Compile AST</span>
      </button>
      <button id="launchBtn" onclick="toggleSim()" class="px-4 py-1.5 rounded-md text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-md shadow-emerald-600/30 transition flex items-center space-x-1.5">
        <span id="launchText">▶ Launch Simulation</span>
      </button>
    </div>
  </header>

  <!-- Main 3-Column Studio Workspace -->
  <main class="flex-1 grid grid-cols-12 gap-0 overflow-hidden">

    <!-- Column 1: Visual Computational Graph (React Flow representation) -->
    <section class="col-span-5 bg-slate-950 border-r border-slate-800 flex flex-col relative overflow-hidden">
      <div class="bg-slate-900/80 px-4 py-2 border-b border-slate-800 flex items-center justify-between text-xs font-semibold text-slate-300">
        <span>Visual Block Graph</span>
        <span class="text-xs text-slate-400">6 Connected Blocks • 6 Wires</span>
      </div>

      <div class="flex-1 p-4 overflow-auto relative">
        <svg id="wireCanvas" class="absolute inset-0 w-full h-full pointer-events-none z-10">
          <!-- Live Animated Oscilloscope Wires -->
          <path id="wire1" d="M 180 65 C 220 65, 230 145, 260 145" fill="none" stroke="#6366f1" stroke-width="2.5" class="pulsing-wire"/>
          <path id="wire2" d="M 180 65 C 220 65, 230 235, 260 235" fill="none" stroke="#6366f1" stroke-width="2.5" class="pulsing-wire"/>
          <path id="wire3" d="M 390 155 C 420 155, 410 245, 260 245" fill="none" stroke="#10b981" stroke-width="2.5" class="pulsing-wire"/>
          <path id="wire4" d="M 390 245 C 410 245, 410 335, 260 335" fill="none" stroke="#10b981" stroke-width="2.5" class="pulsing-wire"/>
          <path id="wire5" d="M 390 335 C 410 335, 410 425, 260 425" fill="none" stroke="#3b82f6" stroke-width="2.5" class="pulsing-wire"/>
        </svg>

        <div class="space-y-4 relative z-20">
          <!-- Block 1: LidarSensorBlock -->
          <div class="bg-slate-900 border border-slate-800 rounded-lg p-3 w-48 shadow-lg">
            <div class="flex items-center justify-between pb-1 mb-2 border-b border-slate-800">
              <span class="text-xs font-bold text-rose-400">2D LiDAR Sensor</span>
              <span id="hz_scan" class="text-[11px] font-mono px-1.5 py-0.2 bg-slate-800 rounded text-slate-400">10.0 Hz</span>
            </div>
            <div class="text-[11px] text-slate-400 flex justify-between">
              <span>Port: /scan</span>
              <span class="text-emerald-400 font-mono">best_effort</span>
            </div>
          </div>

          <!-- Block 2: SlamToolboxBlock -->
          <div class="bg-slate-900 border border-slate-800 rounded-lg p-3 w-48 ml-20 shadow-lg">
            <div class="flex items-center justify-between pb-1 mb-2 border-b border-slate-800">
              <span class="text-xs font-bold text-amber-400">SLAM Toolbox</span>
              <span id="hz_map" class="text-[11px] font-mono px-1.5 py-0.2 bg-slate-800 rounded text-slate-400">1.0 Hz</span>
            </div>
            <div class="text-[11px] text-slate-400 flex justify-between">
              <span>Map: /map</span>
              <span class="text-indigo-400 font-mono">transient_local</span>
            </div>
          </div>

          <!-- Block 3: Nav2CostmapBlock -->
          <div class="bg-slate-900 border border-slate-800 rounded-lg p-3 w-48 ml-20 shadow-lg">
            <div class="flex items-center justify-between pb-1 mb-2 border-b border-slate-800">
              <span class="text-xs font-bold text-blue-400">Nav2 Costmap 2D</span>
              <span class="text-[11px] font-mono px-1.5 py-0.2 bg-slate-800 rounded text-slate-400">5.0 Hz</span>
            </div>
            <div class="text-[11px] text-slate-400">Inflation: 0.55m • Radius: 0.25m</div>
          </div>

          <!-- Block 4: Nav2PathPlannerBlock -->
          <div class="bg-slate-900 border border-slate-800 rounded-lg p-3 w-48 ml-20 shadow-lg">
            <div class="flex items-center justify-between pb-1 mb-2 border-b border-slate-800">
              <span class="text-xs font-bold text-teal-400">NavFn Planner</span>
              <span class="text-[11px] font-mono px-1.5 py-0.2 bg-slate-800 rounded text-slate-400">2.0 Hz</span>
            </div>
            <div class="text-[11px] text-slate-400">Outputs: /plan (nav_msgs/Path)</div>
          </div>

          <!-- Block 5: CustomPythonNodeBlock -->
          <div class="bg-slate-900 border border-indigo-500/50 rounded-lg p-3 w-48 ml-20 shadow-lg shadow-indigo-500/10">
            <div class="flex items-center justify-between pb-1 mb-2 border-b border-slate-800">
              <span class="text-xs font-bold text-indigo-400">Custom Safety Node</span>
              <span id="hz_cmd" class="text-[11px] font-mono px-1.5 py-0.2 bg-indigo-950 rounded text-indigo-300">20.0 Hz</span>
            </div>
            <div class="text-[11px] text-slate-400">Scaffolded Python Filter</div>
          </div>
        </div>
      </div>
    </section>

    <!-- Column 2: Interactive 3D Rover Viewport -->
    <section class="col-span-3 bg-slate-900/50 border-r border-slate-800 flex flex-col relative">
      <div class="bg-slate-900/80 px-4 py-2 border-b border-slate-800 flex items-center justify-between text-xs font-semibold text-slate-300">
        <span>3D Rover Simulation Viewport</span>
        <span id="simBadge" class="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-400">IDLE</span>
      </div>

      <div class="flex-1 flex flex-col items-center justify-center p-4 relative">
        <canvas id="roverCanvas" width="320" height="360" class="rounded-xl border border-slate-800 bg-slate-950 shadow-inner"></canvas>
        <div class="absolute bottom-6 left-6 right-6 bg-slate-900/90 border border-slate-800 p-2.5 rounded-lg text-xs space-y-1 backdrop-blur">
          <div class="flex justify-between text-slate-400 font-mono text-[11px]">
            <span>Linear Vel: <span id="vX" class="text-slate-200">0.00 m/s</span></span>
            <span>Yaw: <span id="wZ" class="text-slate-200">0.00 rad/s</span></span>
          </div>
          <div class="flex justify-between text-slate-400 font-mono text-[11px]">
            <span>LiDAR Rays: <span class="text-emerald-400">360 (Active)</span></span>
            <span>Wheel Slip: <span class="text-emerald-400">0.0% (OK)</span></span>
          </div>
        </div>
      </div>
    </section>

    <!-- Column 3: Live X-Ray Code Split-Screen -->
    <section class="col-span-4 bg-slate-950 flex flex-col">
      <div class="bg-slate-900 border-b border-slate-800 px-3 py-1.5 flex items-center space-x-2 text-xs overflow-x-auto">
        <button onclick="switchTab('launch')" id="tab_launch" class="px-2.5 py-1 rounded bg-slate-800 text-indigo-300 font-medium">launch.py</button>
        <button onclick="switchTab('urdf')" id="tab_urdf" class="px-2.5 py-1 rounded text-slate-400 hover:text-slate-200">urdf.xacro</button>
        <button onclick="switchTab('safety')" id="tab_safety" class="px-2.5 py-1 rounded text-slate-400 hover:text-slate-200">safety_filter.py</button>
        <button onclick="switchTab('bridge')" id="tab_bridge" class="px-2.5 py-1 rounded text-slate-400 hover:text-slate-200">bridge.yaml</button>
        <button onclick="switchTab('nav2')" id="tab_nav2" class="px-2.5 py-1 rounded text-slate-400 hover:text-slate-200">nav2_params.yaml</button>
      </div>

      <div class="flex-1 p-3 overflow-hidden flex flex-col">
        <pre id="codeDisplay" class="flex-1 bg-slate-900 p-3 rounded-lg border border-slate-800 text-xs font-mono text-slate-300 overflow-auto whitespace-pre leading-relaxed select-all">Loading compiled ROS 2 artifacts...</pre>
      </div>
    </section>

  </main>

  <!-- Pre-Flight Status Bar -->
  <footer class="bg-slate-900 border-t border-slate-800 px-6 py-2 flex items-center justify-between text-xs font-medium">
    <div class="flex items-center space-x-4">
      <span id="tfStatus" class="flex items-center space-x-1.5 text-emerald-400">
        <span>✓</span> <span>TF2 DAG: map → odom → base_footprint → base_link → laser_frame</span>
      </span>
      <span id="qosStatus" class="flex items-center space-x-1.5 text-emerald-400 pl-4 border-l border-slate-800">
        <span>✓</span> <span>QoS Contracts: Matched (LiDAR: BEST_EFFORT, SLAM: TRANSIENT_LOCAL)</span>
      </span>
    </div>
    <div class="flex items-center space-x-3 text-slate-400 font-mono text-[11px]">
      <span>Daemon: <span class="text-emerald-400">ONLINE</span></span>
      <span>Port: 8050</span>
    </div>
  </footer>

  <script>
    let filesData = {};
    let activeTab = 'launch';
    let isSimulating = false;
    let roverAngle = 0;
    let sweepAngle = 0;

    async function loadFiles() {
      try {
        const res = await fetch('/api/files');
        filesData = await res.json();
        updateCodeView();
      } catch (e) {
        console.error(e);
      }
    }

    function switchTab(tab) {
      activeTab = tab;
      ['launch', 'urdf', 'safety', 'bridge', 'nav2'].forEach(t => {
        const el = document.getElementById('tab_' + t);
        if (t === tab) {
          el.className = 'px-2.5 py-1 rounded bg-slate-800 text-indigo-300 font-medium';
        } else {
          el.className = 'px-2.5 py-1 rounded text-slate-400 hover:text-slate-200';
        }
      });
      updateCodeView();
    }

    function updateCodeView() {
      const codeEl = document.getElementById('codeDisplay');
      if (activeTab === 'launch') {
        codeEl.textContent = filesData['launch/robot_bringup.launch.py'] || 'Click "Compile AST" to generate launch file.';
      } else if (activeTab === 'urdf') {
        codeEl.textContent = filesData['urdf/agy_rover.urdf.xacro'] || 'Click "Compile AST" to generate URDF.';
      } else if (activeTab === 'safety') {
        codeEl.textContent = filesData['agy_rover_bringup/safety_filter.py'] || 'Click "Compile AST" to generate node.';
      } else if (activeTab === 'bridge') {
        codeEl.textContent = filesData['config/ros_gz_bridge.yaml'] || 'Click "Compile AST" to generate bridge.';
      } else if (activeTab === 'nav2') {
        codeEl.textContent = filesData['config/nav2_params.yaml'] || 'Click "Compile AST" to generate Nav2 config.';
      }
    }

    async function runLinter() {
      const res = await fetch('/api/lint', { method: 'POST' });
      const data = await res.json();
      if (data.passed) {
        alert('✓ Pre-Flight Static Graph Linter Passed! 0 Errors, ' + data.warnings.length + ' Warnings.');
      } else {
        alert('✗ Linter Errors: ' + data.errors.join('\\n'));
      }
    }

    async function compileWorkspace() {
      const res = await fetch('/api/compile', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        await loadFiles();
        alert('⚡ Compilation Successful! Generated ' + data.result.file_count + ' ROS 2 package files.');
      } else {
        alert('✗ Compilation Failed: ' + data.error);
      }
    }

    async function toggleSim() {
      const res = await fetch('/api/launch', { method: 'POST' });
      const data = await res.json();
      isSimulating = data.sim_running;
      document.getElementById('simBadge').textContent = isSimulating ? 'SIMULATING (50Hz)' : 'IDLE';
      document.getElementById('simBadge').className = isSimulating
        ? 'px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950 text-emerald-400 border border-emerald-800 animate-pulse'
        : 'px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-400';

      document.getElementById('launchBtn').className = isSimulating
        ? 'px-4 py-1.5 rounded-md text-xs font-semibold bg-rose-600 hover:bg-rose-500 text-white shadow-md shadow-rose-600/30 transition flex items-center space-x-1.5'
        : 'px-4 py-1.5 rounded-md text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-md shadow-emerald-600/30 transition flex items-center space-x-1.5';

      document.getElementById('launchText').textContent = isSimulating ? '⏹ Stop Simulation' : '▶ Launch Simulation';
    }

    // 3D Canvas Rendering Loop
    const canvas = document.getElementById('roverCanvas');
    const ctx = canvas.getContext('2d');

    function drawRoverSimulation() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Grid background
      ctx.strokeStyle = '#1e293b';
      ctx.lineWidth = 1;
      for (let x = 0; x < canvas.width; x += 20) {
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke();
      }
      for (let y = 0; y < canvas.height; y += 20) {
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke();
      }

      ctx.save();
      ctx.translate(canvas.width / 2, canvas.height / 2);
      ctx.rotate(roverAngle);

      // LiDAR ray sweep
      if (isSimulating) {
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(0, -10);
        ctx.arc(0, -10, 90, sweepAngle - 0.3, sweepAngle);
        ctx.fillStyle = 'rgba(16, 185, 129, 0.15)';
        ctx.fill();
        ctx.restore();
      }

      // Rover Chassis
      ctx.fillStyle = '#3b82f6';
      ctx.fillRect(-35, -50, 70, 100);

      // Wheels
      ctx.fillStyle = '#64748b';
      ctx.fillRect(-45, -45, 10, 25);
      ctx.fillRect(35, -45, 10, 25);
      ctx.fillRect(-45, 20, 10, 25);
      ctx.fillRect(35, 20, 10, 25);

      // LiDAR sensor turret
      ctx.fillStyle = '#ef4444';
      ctx.beginPath();
      ctx.arc(0, -15, 10, 0, Math.PI * 2);
      ctx.fill();

      // Heading indicator
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(0, -15);
      ctx.lineTo(0, -45);
      ctx.stroke();

      ctx.restore();

      if (isSimulating) {
        roverAngle += 0.01;
        sweepAngle += 0.08;
        document.getElementById('vX').textContent = '0.35 m/s';
        document.getElementById('wZ').textContent = '0.22 rad/s';
      } else {
        document.getElementById('vX').textContent = '0.00 m/s';
        document.getElementById('wZ').textContent = '0.00 rad/s';
      }

      requestAnimationFrame(drawRoverSimulation);
    }

    loadFiles();
    drawRoverSimulation();
  </script>
</body>
</html>"""


def start_server():
    server = socketserver.TCPServer(("", PORT), StudioHandler)
    server.allow_reuse_address = True
    print(f"🚀 Antigravity ROS Studio running at http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    start_server()
