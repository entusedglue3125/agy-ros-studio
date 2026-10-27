# Agent 2 Research Report: Architecture, Advantages, Limitations & MCP Code Reuse

**Author:** Agent 2 (Core Systems & Runtime Architect)  
**Date:** October 2026  
**Status:** Completed  
**Artifact Target:** `research/raw_reports/agent_2_architecture.md`

---

## 1. Executive Summary

Building an autonomous visual IDE for ROS 2 (supporting both Humble LTS and Jazzy Jalisco) requires balancing two opposing forces:
1. **Low-Latency Middleware Interactivity:** Deep introspection of the active DDS network, topic Hz monitoring, dynamic QoS matching, and lifecycle node tracking.
2. **Deterministic Code Generation & Graph Validation:** Compiling visual block graphs into clean, standard ROS 2 Python packages, launch files, and URDF/Xacro XML with zero runtime magic.

This report specifies the concrete Python modules to extract and reuse from `rde-mcp-ros-2` and `wise-vision-ros2-mcp`, evaluates the architectural trade-offs of Native Qt vs. Web-based UI runtimes, analyzes static graph validation capabilities, and documents the engineering solutions for the hardest edge cases in robotics simulation: DDS process zombies, GPU starvation, 3D TF frame orientation, and the "Abstraction Ceiling."

---

## 2. MCP Code Reuse & Module Extraction Blueprint

Rather than writing low-level `rclpy` bindings and subprocess monitors from scratch, our architecture reuses production-tested components from the cloned reference repositories:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        ANTIGRAVITY IDE CORE                            │
└──────────────────┬─────────────────────────────────┬───────────────────┘
                   │                                 │
                   ▼                                 ▼
┌──────────────────────────────────────┐  ┌──────────────────────────────┐
│  wise-vision-ros2-mcp (rclpy Core)   │  │   rde-mcp-ros-2 (CLI/Doctor) │
├──────────────────────────────────────┤  ├──────────────────────────────┤
│ • Dynamic QoS Discovery              │  │ • ros2 doctor Structured     │
│   (ros2_manager.py: L645-675)        │  │   Diagnostics (L1178-1248)   │
│ • Monotonic Topic Hz & Streaming     │  │ • Node/Param Inspection      │
│   (ros2_manager.py: L423-430)        │  │   (server.py: L400-500)      │
│ • PointCloud2 & OccupancyGrid to     │  │ • rosbag2 Recording/Playback │
│   WebGL (ros2_manager_extended.py)   │  │   (server.py: L800-950)      │
│ • DDS Discovery Warmup Engine        │  │                              │
│   (ros2_manager.py: L561-643)        │  │                              │
└──────────────────────────────────────┘  └──────────────────────────────┘
```

### 2.1 Reusable Modules from `mcp_servers/wise-vision-ros2-mcp`

#### A. Dynamic QoS Auto-Detection (`server/ros2_manager.py`, lines 645–675)
- **Function:** `ROS2Manager.get_qos_profile_for_topic(node, topic_name)`
- **Mechanism:** Queries `node.get_publishers_info_by_topic(topic_name)` and inspects each endpoint's `qos_profile.reliability` (`RELIABLE` vs `BEST_EFFORT`) and `qos_profile.durability` (`TRANSIENT_LOCAL` vs `VOLATILE`).
- **Reuse Application:** In our Visual Topic Wire Linter, when a user connects a block subscriber to an existing publisher, this module runs in the background. If the publisher is emitting `sensor_data` (Best-Effort) and the block defaults to `SystemDefault` (Reliable), the IDE flags an immediate visual warning and auto-reconfigures the block's QoS dropdown.

#### B. High-Precision Topic Hz & Monotonic Streaming (`server/ros2_manager.py`, lines 410–435)
- **Functions:** `_MCPStreamSession` and `ROS2Manager.start_stream()` / `stream_next()`
- **Mechanism:** Maintains a thread-safe sliding window tracking message receipts using `time.monotonic()`:
  ```python
  now = time.monotonic()
  session.rx_count += 1
  session.last_rx_monotonic = now
  ```
- **Reuse Application:** Powers the IDE's **Animated Topic Wire Oscilloscope**. Wires between blocks visually pulse at the measured Hz, immediately showing students if a camera is streaming at 30Hz, an odometry loop is running at 50Hz, or if a topic has died (0Hz).

#### C. Nav2 Map & PointCloud2 Binary Serialization (`server/ros2_manager_extended.py`)
- **Functions:**
  - `ExtendedROS2Manager.get_single_map_from_topic()` (lines 250–320): Converts `nav_msgs/OccupancyGrid` into compressed image buffers with metadata (`origin`, `resolution`).
  - `ROS2Manager._extract_pointcloud2_xyz_b64()` (lines 213–260): Unpacks binary IEEE 754 float fields (`x`, `y`, `z`, and RGB/intensity) from `sensor_msgs/PointCloud2` and downsamples via configurable strides.
- **Reuse Application:** Streams map layers and 3D depth scans directly over WebSockets to the IDE's WebGL viewport, eliminating the need to launch an external heavy RViz2 window.

#### D. DDS Discovery Warmup Engine (`server/ros2_manager.py`, lines 561–643)
- **Function:** `ROS2Manager.warm_up_discovery()`
- **Mechanism:** Cycles `rclpy.spin_once` and monitors graph delta snapshots (`_graph_snapshot()`) until the node and topic count stabilize over a configurable duration (`MCP_ROS_DISCOVERY_STABLE_SEC`).
- **Reuse Application:** Prevents intermittent "node not found" and "topic missing" race conditions when launching multi-node launch files inside Docker or student laptops.

---

### 2.2 Reusable Modules from `mcp_servers/rde-mcp-ros-2`

#### A. Structured `ros2 doctor` System Health Engine (`src/rde_mcp_ros2/server.py`, lines 1178–1248)
- **Function:** `run_doctor(report=False, include_warnings=True)`
- **Mechanism:** Spawns `ros2 doctor`, parses bracketed terminal tokens (`[ERROR]`, `[WARNING]`, `[OK]`), and constructs a structured JSON diagnostic payload:
  ```python
  checks.append({
      "name": name,
      "status": status,
      "details": details
  })
  ```
- **Reuse Application:** Integrated into the IDE status bar as a continuous "Pre-Flight Check". Before a student clicks "Launch Rover", the IDE checks network multicast configuration, DDS domain IDs, package build stamps, and ROS environment variables (`RMW_IMPLEMENTATION`, `ROS_DOMAIN_ID`).

#### B. Dynamic Parameter Inspection & Tuning (`src/rde_mcp_ros2/server.py`, lines 400–500)
- **Functions:** `list_parameters(node_name)`, `get_parameter(node_name, param_name)`, `set_parameter(node_name, param_name, value)`
- **Reuse Application:** Powers live parameter sliders in the IDE's visual blocks (e.g., tweaking `max_vel_x`, `inflation_radius`, or PID gains without restarting the launch stack).

---

## 3. UI Runtime Architecture: Native Qt vs. Web-Based Electron/React Flow

A critical architectural decision is whether to build the visual IDE as a native C++/Qt application embedding `librviz` or as a web-based Electron app leveraging React Flow, Three.js/WebGL, and headless Gazebo.

### 3.1 Comprehensive Trade-Off Comparison

| Metric | Native C++ / Qt6 (`librviz`) | Web-Based (React Flow + Electron + WebGL) | Architectural Decision |
| :--- | :--- | :--- | :--- |
| **Node Graph UI Flexibility** | Rigid. QGraphicsView/NodeEditor requires extensive boilerplate for animations, responsive docking, and theming. | **Exceptional.** React Flow provides declarative node/port layouts, dynamic bezier wires, custom SVG badges, and CSS animations. | **Web-Based wins.** |
| **3D Rendering Performance** | High native performance (OGRE / OpenGL via `librviz_rendering`). Direct GPU access. | Moderate-High (Three.js / WebGL / WebGPU). Sufficient for student rovers (50k points @ 60 FPS). | **Native Qt slight edge, but WebGL is more than adequate.** |
| **Memory & Process Footprint** | Low RAM (~150MB). Direct in-process C++ bindings. | Higher RAM (~350–550MB for Chromium + V8 + Node). | **Acceptable cost for modern development machines.** |
| **Cross-Platform / Remote Web** | Difficult. Requires native compilation per distro/OS; impossible to run over a web browser. | **Native Cloud/Web support.** Electron packages for desktop, while the same React codebase runs in Chrome for cloud labs. | **Web-Based decisive win.** |
| **ROS 2 Middleware Coupling** | Hard-linked to specific Ubuntu/ROS 2 debian versions (Humble vs Jazzy ABI incompatibility). | **Decoupled.** Communicates over JSON-RPC / WebSocket (`rosbridge` or MCP daemon). Works with any ROS 2 distro or container. | **Web-Based decisive win.** |
| **Ecosystem & UI Component Velocity**| Slow C++ GUI iteration. Few modern UI component libraries. | Rapid. Monolithic ecosystem (Tailwind CSS, Lucide icons, Monaco editor, KaTeX). | **Web-Based decisive win.** |

### 3.2 Chosen Hybrid Architecture
We adopt a **Decoupled Hybrid Architecture**:
- **Frontend Presentation Layer:** Electron + React 18 + React Flow + Three.js / WebGL 3D Viewport + Monaco Editor.
- **Middleware Daemon (Sidecar):** Python 3.10/3.12 daemon running FastMCP + `rclpy`, embedding the extracted modules from `wise-vision-ros2-mcp` and `rde-mcp-ros-2`.
- **Simulation Server:** Headless Gazebo Sim (`gz sim -s -r <world.sdf>`) running in the background, bridged via `ros_gz_bridge`.
- **Communication Bus:** WebSocket (`ws://127.0.0.1:9090`) for bidirectional JSON-RPC MCP commands, and binary WebSocket for high-bandwidth sensor streams (LiDAR, camera images).

---

## 4. Static Graph Validation vs. Hard Limitations & Workarounds

### 4.1 Static Graph Validation Advantages (Catching Errors Before Launch)
Standard ROS 2 development is notoriously runtime-failure-prone. Our IDE acts as a **Static Compiler & Linter** prior to code execution:

1. **Acyclic TF2 Frame Graph Verification:**
   - *Problem:* A robot state publisher fails or Nav2 crashes if there are cycles in the TF tree or disconnected transform islands (e.g., `laser_frame` has parent `base_link`, but `base_link` has no transform to `odom`).
   - *Static Check:* As blocks are connected, the IDE builds a Directed Acyclic Graph (DAG) of all coordinate frames. If a cycle or island is detected, the compiler highlights the disconnected block with an exact fix: *"No transform between 'odom' and 'base_footprint'. Add an Odometry Publisher or DiffDrive block."*
2. **Compile-Time QoS Compatibility Linter:**
   - *Problem:* DDS strictly enforces compatibility matrices. If a subscriber requests `RELIABLE` while a publisher offers `BEST_EFFORT`, the DDS participant silently drops all packets without raising an exception.
   - *Static Check:* The compiler cross-checks the QoS properties of paired block ports. If a mismatch occurs, the wire turns orange with a warning tooltip.
3. **Topic Name & Type Schema Enforcement:**
   - *Problem:* Typos like `/cmd_vel` vs `/cmd_velocity` or wiring a `geometry_msgs/Twist` output to a `nav_msgs/Odometry` input.
   - *Static Check:* Port types are strongly typed. A `Twist` output port will refuse a magnetic connection to an `Odometry` input port, eliminating type mismatches.

---

### 4.2 Hard Limitations & Engineering Workarounds

#### Limitation 1: The "Abstraction Ceiling"
*Problem:* Visual block tools often hit an "abstraction ceiling" where advanced students cannot implement custom state machines, custom filters, or novel algorithms because no block exists for them.  
*Engineering Workaround:*
- **The Scaffolded Python Node Block:** A hybrid block containing an embedded Monaco Python editor. The student visually defines topic inputs and outputs (which auto-generates the `create_subscription` and `create_publisher` boilerplate), while the block provides an indented `def callback(self, msg):` code window with full Python auto-completion.
- **Two-Way Code Synchronization:** The compiler uses an explicit JSON Abstract Syntax Tree (AST) representation. Code is generated deterministically from the AST using Jinja2 templates.

#### Limitation 2: CPU & GPU Starvation
*Problem:* Running Gazebo physics, RViz rendering, Nav2 costmaps, and an Electron/Chromium IDE simultaneously can overwhelm standard student laptops (4 cores, 8GB RAM, integrated Intel Iris/UHD graphics).  
*Engineering Workaround:*
- **Headless Gazebo Execution (`gz sim -s`):** Never run the heavy Gazebo GUI Qt client. Gazebo runs headless with the physics update loop decoupled from rendering.
- **Client-Side WebGL Rendering:** The Electron frontend renders the robot model and LiDAR points directly in WebGL via Three.js.
- **Adaptive Decimation:** Point clouds and costmaps are decimated (e.g., 10Hz to 2Hz, 100k points to 5k points) when laptop battery or frame drops are detected.

#### Limitation 3: 3D Spatial TF Configuration (Roll, Pitch, Yaw & Quaternions)
*Problem:* Beginners struggle with 3D coordinate frames, Euler angle conventions (extrinsic vs. intrinsic), and quaternion conversions, leading to inverted LiDAR scans or wheels rotating around the wrong axis.  
*Engineering Workaround:*
- **Interactive 3D Transform Gizmo:** When editing a joint block in the IDE, a live 3D transform gizmo appears directly on the robot model. Dragging the rotation rings visually updates the URDF `origin rpy="..."` and joint `axis xyz="..."` parameters in real time.

#### Limitation 4: Zombie DDS & Gazebo Processes
*Problem:* Terminating a ROS 2 launch file via Electron often leaves orphaned DDS discovery daemons, background `gz-sim` servers, or `nav2` lifecycle nodes occupying domain IDs and TCP/UDP ports.  
*Engineering Workaround:*
- **Linux Process Group & PID Tree Reclamation:** When launching nodes, the daemon executes them inside a dedicated POSIX process group (`os.setpgrp()`). On stop, the daemon sends `SIGTERM` followed by a grace-period `SIGKILL` to the entire process group:
  ```python
  import os, signal, psutil
  def terminate_process_tree(pgid):
      try:
          os.killpg(pgid, signal.SIGTERM)
          time.sleep(1.0)
          os.killpg(pgid, signal.SIGKILL)
      except ProcessLookupError:
          pass
  ```
- **Pre-Flight DDS Port Sweep:** Before every new launch, the daemon sweeps for lingering ROS 2 and Gazebo sockets using `psutil`, cleanly clearing locks on `~/.gz/sim` and shared memory segments (`/dev/shm`).
