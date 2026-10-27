# Example Usage Scenarios

Here are some example conversations you can have with your AI assistant once the ROS 2 MCP Server is connected.

## Getting Started

### Basic System Introspection

**You:** "What ROS 2 nodes are currently running?"

**AI:** Uses `get_nodes()` to list all active nodes.

---

**You:** "Show me all the topics being published right now"

**AI:** Uses `list_topics()` to show active topics with their types.

---

**You:** "What services are available?"

**AI:** Uses `list_services()` to enumerate all ROS 2 services.

## Working with Topics

### Inspecting Topics

**You:** "What's being published on /camera/image_raw?"

**AI:** Uses `get_topic_info("/camera/image_raw")` then `echo_topic()` to show sample messages.

---

**You:** "Show me the last 5 messages from /odom"

**AI:** Uses `echo_topic()` with appropriate parameters.

### Publishing to Topics

**You:** "Publish a Twist message to /cmd_vel to move the robot forward at 0.5 m/s"

**AI:** Uses `publish_to_topic()` with the appropriate message structure:
```python
{
  "linear": {"x": 0.5, "y": 0, "z": 0},
  "angular": {"x": 0, "y": 0, "z": 0}
}
```

## Parameter Management

**You:** "What's the current maximum speed parameter for the nav2 controller?"

**AI:** Uses `list_parameters()` to find parameters, then `get_parameter()` to retrieve the value.

---

**You:** "Set the robot's base frame to 'base_footprint'"

**AI:** Uses `set_parameter()` to update the configuration.

## Service Calls

**You:** "Clear the costmap"

**AI:** Uses `list_services()` to find the clear_costmap service, then `call_service()` to trigger it.

---

**You:** "Spawn a new entity in Gazebo"

**AI:** Uses `get_service_type()` to understand the service interface, then `call_service()` with appropriate parameters.

## Bag File Operations

**You:** "Record all camera and lidar topics for the next 60 seconds"

**AI:** Uses `list_topics()` to find camera/lidar topics, then `record_bag()`:
```python
record_bag(
    topics=["/camera/image_raw", "/scan"],
    output_file="sensor_data.bag",
    duration=60
)
```

---

**You:** "What's in the recording from yesterday?"

**AI:** Uses `get_bag_info("yesterday_data.bag")` to show topics, message counts, and duration.

## Launch Files

**You:** "Launch the navigation stack with custom parameters"

**AI:** Uses `list_launch_files()` to find nav2 launch files, `get_launch_parameters()` to see options, then `launch_file()` with your parameters.

---

**You:** "Start the robot bringup"

**AI:** Uses `launch_file("robot_bringup", "launch.py")` from the appropriate package.

## Package Management

**You:** "What executables are in the nav2_bringup package?"

**AI:** Uses `package_executables("nav2_bringup")` to list all runnable nodes.

---

**You:** "Show me the dependencies for my custom package"

**AI:** Uses `get_package_manifest("my_robot_package")` to parse package.xml.

## Lifecycle Management

**You:** "Configure and activate the lifecycle camera node"

**AI:** Uses `get_lifecycle_state()` to check current state, then `set_lifecycle_transition()` to move through:
1. unconfigured → configuring → inactive
2. inactive → activating → active

## Advanced Workflows

### Debugging a Robot Issue

**You:** "The robot isn't moving. Can you help me debug?"

**AI:** Performs a systematic check:
1. `get_nodes()` - Verify all required nodes are running
2. `list_topics()` - Check if /cmd_vel has publishers
3. `echo_topic("/cmd_vel")` - See if commands are being sent
4. `get_parameter()` - Check velocity limits
5. `run_doctor()` - Run ROS 2 diagnostics

### Setting Up a New Workspace

**You:** "Help me set up a new navigation workspace with proper parameters"

**AI:** Guides you through:
1. `list_packages()` - Verify nav2 is installed
2. `get_launch_parameters()` - Show available config options
3. Creates parameter files with appropriate values
4. `launch_file()` - Starts the navigation stack

### Data Collection

**You:** "I need to collect synchronized camera and IMU data for 10 minutes"

**AI:** 
1. `list_topics()` - Find all camera and IMU topics
2. `record_bag()` - Start recording with:
   - All /camera/* topics
   - All /imu/* topics
   - Duration: 600 seconds
3. Monitors the recording
4. `get_bag_info()` - Verifies data was collected

## Interface Inspection

**You:** "What's the structure of the NavToPose action?"

**AI:** Uses `show_interface("nav2_msgs/action/NavToPose")` to display the complete action definition.

---

**You:** "Show me all message types related to navigation"

**AI:** Uses `list_interfaces("msg")` with filtering for navigation-related types.

## System Monitoring

**You:** "Monitor the robot's status and alert me if anything goes wrong"

**AI:** Sets up continuous monitoring:
1. `get_nodes()` - Watch for node crashes
2. `echo_topic("/diagnostics")` - Monitor system health
3. `list_lifecycle_nodes()` + `get_lifecycle_state()` - Check lifecycle states
4. Alerts on any anomalies

---

These examples demonstrate the power of having ROS 2 introspection available to AI assistants. The AI can understand your intent and use the appropriate tools to accomplish complex tasks!
