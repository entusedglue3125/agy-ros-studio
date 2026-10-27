# Agent 4 Research Report: Sim-to-Real Rover Hardware Bridge Architecture

**Author:** Agent 4 (Hardware Abstraction & Sim-to-Real Systems Engineer)  
**Date:** October 2026  
**Status:** Completed  
**Artifact Target:** `research/raw_reports/agent_4_sim2real.md`

---

## 1. Executive Summary

One of the greatest pedagogical triumphs in robotics education occurs when a student designs an autonomous navigation pipeline in simulation and then deploys the exact same algorithm onto a physical robot without altering their autonomy stack. 

In conventional education, this transition is fraught with disaster: physical hardware drivers use different topic names, require serial protocol daemons, suffer from uncalibrated wheel slip, saturate Wi-Fi networks with DDS multicast discovery, and overwhelm single-board computers (SBCs).

This report specifies a **Modular Hardware Abstraction Block (HAB)** architecture that enables 1-click hot-swapping between simulated Gazebo rovers and physical hardware (micro-ROS, serial microcontroller, or `ros2_control`), defines the standard ROS 2 interface contract, and establishes engineering solutions for real-world hardware degradation.

---

## 2. Standardized Hardware Abstraction Layer (HAL) Interface Contract

To make physical and simulated robots interchangeable, both targets must strictly adhere to the standard ROS 2 Mobile Robot Interface Contract:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   HIGH-LEVEL AUTONOMY (SLAM & NAV2)                    │
│                                                                        │
│   Subscriptions:                  Publications:                        │
│   • /odom    (nav_msgs/Odometry)  • /cmd_vel (geometry_msgs/Twist)     │
│   • /scan    (sensor_msgs/LaserScan)                                   │
│   • /imu     (sensor_msgs/Imu)                                         │
│   • /tf, /tf_static (tf2_msgs/TFMessage)                               │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (Identical Topic & Type Interface)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                 MODULAR HARDWARE ABSTRACTION BLOCK                     │
├───────────────────────────────────┬────────────────────────────────────┤
│     TARGET A: SIMULATION          │        TARGET B: PHYSICAL HARDWARE │
│  [Gazebo Simulated 4WD Rover]     │  [Physical Rover: micro-ROS/Serial]│
│                                   │                                    │
│  • gz-sim-diff-drive-system       │  • micro_ros_agent / pyserial      │
│  • gz-sim-sensors (LiDAR/IMU)     │  • Microcontroller (ESP32 / Teensy)│
│  • ros_gz_bridge topics           │  • Physical YDLidar/RPLidar node   │
│  • Simulated /clock               │  • Physical BNO055/MPU6050 node    │
└───────────────────────────────────┴────────────────────────────────────┘
```

### 2.1 The Four Sacred Contract Channels
1. **Motion Actuation (`/cmd_vel`):**  
   - Message Type: `geometry_msgs/msg/Twist` (or `TwistStamped` in Jazzy)
   - Rates: 10Hz to 50Hz
   - Semantics: $v_x$ (forward linear velocity in m/s), $\omega_z$ (rotational yaw velocity in rad/s).
2. **Kinematic Odometry (`/odom`):**  
   - Message Type: `nav_msgs/msg/Odometry`
   - Frame IDs: `header.frame_id = "odom"`, `child_frame_id = "base_footprint"` (or `base_link`)
   - Rates: 20Hz to 50Hz
   - Includes covariance matrices for pose and twist.
3. **Planar Spatial Perception (`/scan`):**  
   - Message Type: `sensor_msgs/msg/LaserScan`
   - Frame ID: `header.frame_id = "laser_frame"`
   - Rates: 5Hz to 15Hz
   - Must publish with `SensorDataQoS` (`BEST_EFFORT`, `VOLATILE`).
4. **Inertial Dynamics (`/imu` or `/imu/data`):**  
   - Message Type: `sensor_msgs/msg/Imu`
   - Frame ID: `header.frame_id = "imu_link"`
   - Rates: 50Hz to 100Hz
   - Includes angular velocity and linear acceleration.

---

## 3. Hot-Swappable Hardware Block Specifications

The visual IDE defines a unified category called `Robotics Hardware Target`. A student can drop either of the following blocks onto their canvas, wire them to Nav2, and toggle between them via a single drop-down switch:

### 3.1 Block Specification A: `Gazebo Simulated 4WD Rover`
- **Compiler Output:**
  - Injects Gazebo plugins into `robot.urdf`:
    ```xml
    <gazebo>
      <plugin filename="gz-sim-diff-drive-system" name="gz::sim::systems::DiffDrive">
        <left_joint>left_wheel_joint</left_joint>
        <right_joint>right_joint_wheel</right_joint>
        <wheel_separation>0.30</wheel_separation>
        <wheel_radius>0.05</wheel_radius>
        <topic>/cmd_vel</topic>
        <odom_topic>/odom</odom_topic>
        <frame_id>odom</frame_id>
        <child_frame_id>base_footprint</child_frame_id>
      </plugin>
    </gazebo>
    ```
  - Generates `ros_gz_bridge` parameter YAML and launch actions to bridge `/scan`, `/imu`, `/odom`, and `/cmd_vel` between Gazebo Sim and ROS 2.
  - Automatically appends parameter `use_sim_time: True` to all downstream nodes.

### 3.2 Block Specification B: `Physical Rover (micro-ROS / Serial HAL)`
- **Configuration Parameters in Block Inspector:**
  - Bridge Type: `micro-ROS (XRCE-DDS over UDP/Wi-Fi)` or `USB Serial (/dev/ttyUSB0 @ 115200 baud)`
  - Microcontroller Target: `ESP32-S3`, `Teensy 4.1`, or `Raspberry Pi Pico W`
  - LiDAR Driver: `RPLiDAR A1/A2/C1` or `YDLidar X4`
  - IMU Driver: `BNO055 (I2C)` or `MPU6050 / ICM-20948`
- **Compiler Output:**
  - Launch file configures:
    1. `micro_ros_agent` node (listening on UDP port 8888 or serial port).
    2. Physical sensor driver nodes (e.g., `sllidar_ros2` or `ydlidar_ros2_driver_node`) publishing to `/scan`.
    3. Hardware static transforms (`robot_state_publisher` running the physical URDF).
    4. Sets `use_sim_time: False` across the entire graph.

---

## 4. Sim-to-Real Limitations & IDE Mitigation Strategies

Deploying simulation algorithms onto physical robots introduces four major friction points. Our IDE incorporates specific architectural mitigations for each:

```
SIMULATION (Pure Ideal World)               PHYSICAL HARDWARE (Noisy Reality)
┌───────────────────────────┐               ┌───────────────────────────┐
│ • Perfect frictionless math│               │ • Wheel slip & motor deadband
│ • Instantaneous DDS bridge │  ── GAP ──>  │ • Wi-Fi packet dropouts   │
│ • Deterministic wall clock │               │ • IMU drift & lidar noise │
│ • Infinite workstation CPU │               │ • SBC throttling (Pi 4/5) │
└───────────────────────────┘               └───────────────────────────┘
```

### 4.1 Limitation 1: DDS Wi-Fi Congestion & Packet Dropouts
- *The Problem:* Standard DDS (CycloneDDS, FastDDS) relies heavily on UDP multicast discovery (`239.255.0.1`). In university lab rooms with 30 student rovers on a shared Wi-Fi router, multicast floods the 2.4GHz/5GHz spectrum. Packet loss spikes to 40%, causing heartbeat timeouts, dropped `/scan` packets, and lost `/cmd_vel` pulses (causing the rover to jerk or fail safety deadman timeouts).
- *IDE Mitigations:*
  1. **FastDDS Discovery Server Configuration:** The IDE generates a launch script configuring a centralized Discovery Server running on the student's laptop. Micro-ROS and the rover SBC communicate via unicast TCP/UDP rather than broadcast multicast:
     ```bash
     export ROS_DISCOVERY_SERVER="192.168.1.100:11811"
     ```
  2. **Eclipse Zenoh Bridge Alternative:** The IDE provides a 1-click toggle to compile with `zenoh-bridge-ros2dds`, which collapses DDS traffic into a lightweight, multiplexed unicast stream optimized for lossy wireless robotics.
  3. **Safety Watchdog Timer:** The HAL generates an onboard motor safety watchdog on the microcontroller. If no `/cmd_vel` heartbeat is received for >250ms due to Wi-Fi dropout, motors immediately execute a graceful stop.

---

### 4.2 Limitation 2: Sensor Noise & IMU Drift
- *The Problem:* In standard Gazebo simulations, sensors produce pure, noiseless ground-truth math. When placed in the real world, low-cost IMUs (e.g., MPU6050) experience severe gyroscope bias drift ($0.5^\circ/\text{sec}$), and LiDAR range readings fluctuate by $\pm 2\text{cm}$ with occasional mirror/glass dropout points. SLAM mapping fails immediately.
- *IDE Mitigations:*
  1. **Simulated Domain Randomization & Noise Injection:** The IDE's Gazebo generator includes realistic Gaussian noise parameters inside the `<sensor>` SDF blocks by default:
     ```xml
     <noise type="gaussian">
       <mean>0.0</mean>
       <stddev>0.015</stddev>
       <bias_mean>0.00005</bias_mean>
       <bias_stddev>0.000005</bias_stddev>
     </noise>
     ```
     Students learn to write robust algorithms that tolerate noise before ever touching physical hardware.
  2. **Automated IMU Zero-Bias Calibration Tool:** When connected to physical hardware, the IDE provides a "Calibrate IMU" button. The daemon samples the stationary rover for 5 seconds, computes the gyro mean offset, and saves a compensation parameter file.

---

### 4.3 Limitation 3: Odometry Drift & Wheel Slip
- *The Problem:* Skid-steer and differential drive rovers suffer severe lateral wheel scrub and slip when turning on carpet or smooth tile. Pure wheel-encoder odometry quickly drifts off by meters, causing the robot to rotate in the real world while the costmap believes it is driving straight.
- *IDE Mitigations:*
  1. **Integrated `robot_localization` EKF Block:** The IDE provides a visual **Sensor Fusion (EKF)** block configured out-of-the-box. It instantiates `ekf_node` from `robot_localization`, fusing high-rate angular velocity from the IMU with wheel encoder ticks from `/odom` to publish a drift-resilient fused `/odometry/filtered` transform.
  2. **Visual Wheel Slip Diagnostic:** When streaming live telemetry, the IDE monitors the discrepancy between commanded velocity `/cmd_vel` and measured odometry acceleration, flagging a warning if wheel slip exceeds 20%.

---

### 4.4 Limitation 4: Onboard Compute Bottlenecks (Raspberry Pi vs. Laptop)
- *The Problem:* Running a full ROS 2 stack (SLAM-Toolbox, Nav2 planners, costmaps, and computer vision) requires 4+ cores and 4GB+ RAM. Running this directly on an onboard Raspberry Pi 4 causes thermal throttling, frame rate drops below 2Hz, and planning timeouts.
- *IDE Mitigations:*
  1. **Distributed Compute Partitioning Architecture:** The IDE compiler understands network topology. In "Distributed Mode", it compiles two separate launch artifacts with a single click:
     - **Onboard Artifact (Deploy to Pi via SSH):** Low-overhead driver nodes (`micro_ros_agent`, LiDAR driver node, IMU publisher, camera streamer). Consumes <15% CPU.
     - **Offboard Artifact (Run on Student Laptop):** Heavy computational nodes (`slam_toolbox`, `nav2_bringup`, Three.js 3D WebGL visualization, Behavior Tree runner).
  2. **1-Click Remote Deployment:** The IDE incorporates an automated SSH deployment action that transfers the compiled onboard workspace to `rover@192.168.x.x` and launches it systemd-managed or via remote bash execution.
