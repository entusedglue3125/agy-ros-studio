#!/usr/bin/env python3
"""
POSIX Process Manager & Zombie Slayer for Antigravity ROS Studio.
Implements process group isolation via os.setpgrp(), two-phase termination
(SIGTERM -> grace period -> SIGKILL via os.killpg), and pre-flight socket/process sweeps.
"""

import os
import signal
import subprocess
import time
import logging
from typing import Dict, Any, List, Optional
import psutil

logger = logging.getLogger(__name__)


class ManagedProcess:
    def __init__(self, process_id: str, process_type: str, popen_obj: subprocess.Popen, cmd: List[str]):
        self.process_id = process_id
        self.process_type = process_type
        self.popen = popen_obj
        self.cmd = cmd
        self.pid = popen_obj.pid
        self.pgid = os.getpgid(popen_obj.pid)
        self.start_time = time.time()

    def is_alive(self) -> bool:
        return self.popen.poll() is None


class ProcessManager:
    def __init__(self):
        self.active_processes: Dict[str, ManagedProcess] = {}

    def launch_process(
        self,
        process_id: str,
        cmd: List[str],
        process_type: str = "general",
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Launches a command in a dedicated POSIX process group.
        """
        # Ensure any existing process with this ID is terminated first
        if process_id in self.active_processes:
            self.terminate_process(process_id)

        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)

        try:
            p = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=os.setpgrp,  # Creates a new process group: PGID == PID
                env=merged_env,
                cwd=cwd
            )
            managed = ManagedProcess(process_id, process_type, p, cmd)
            self.active_processes[process_id] = managed

            return {
                "success": True,
                "process_id": process_id,
                "pid": managed.pid,
                "pgid": managed.pgid,
                "cmd": cmd
            }
        except Exception as e:
            logger.error(f"Failed to launch process {process_id}: {e}")
            return {"success": False, "error": str(e)}

    def terminate_process(self, process_id: str, grace_period_sec: float = 2.0) -> Dict[str, Any]:
        """
        Gracefully terminates an entire process tree:
        1. Sends SIGTERM to the process group (os.killpg).
        2. Waits up to grace_period_sec for clean exit.
        3. If processes linger, forcefully terminates with SIGKILL.
        """
        managed = self.active_processes.get(process_id)
        if not managed:
            return {"success": True, "message": f"Process {process_id} not found or already stopped."}

        pgid = managed.pgid
        pid = managed.pid

        # Phase 1: SIGTERM
        try:
            os.killpg(pgid, signal.SIGTERM)
        except ProcessLookupError:
            pass  # Already terminated
        except Exception as e:
            logger.warning(f"Error sending SIGTERM to PGID {pgid}: {e}")

        # Wait with timeout
        deadline = time.time() + grace_period_sec
        terminated = False
        while time.time() < deadline:
            if managed.popen.poll() is not None:
                terminated = True
                break
            time.sleep(0.1)

        # Phase 2: SIGKILL if still lingering
        if not terminated:
            logger.warning(f"Process {process_id} (PGID {pgid}) did not terminate gracefully; sending SIGKILL.")
            try:
                os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except Exception as e:
                logger.error(f"Error sending SIGKILL to PGID {pgid}: {e}")

        self.active_processes.pop(process_id, None)
        return {
            "success": True,
            "process_id": process_id,
            "pid": pid,
            "pgid": pgid,
            "graceful": terminated
        }

    def terminate_all(self) -> Dict[str, Any]:
        """
        Terminates all currently managed process groups.
        """
        results = {}
        for pid in list(self.active_processes.keys()):
            results[pid] = self.terminate_process(pid)
        return results

    @staticmethod
    def sweep_zombies(
        target_keywords: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Sweeps the system for orphaned Gazebo, DDS, or ROS 2 processes.
        """
        if target_keywords is None:
            target_keywords = [
                "gz sim",
                "ros2 launch",
                "ros2 run",
                "robot_state_publisher",
                "ros_gz_bridge",
                "parameter_bridge",
                "slam_toolbox",
                "micro_ros_agent"
            ]

        killed = []
        current_pid = os.getpid()

        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                p_info = proc.info
                p_pid = p_info.get("pid")
                if p_pid == current_pid or p_pid == 1:
                    continue

                cmdline = " ".join(p_info.get("cmdline") or [])
                if any(kw in cmdline for kw in target_keywords):
                    # Terminate orphan
                    proc.terminate()
                    try:
                        proc.wait(timeout=1.0)
                    except psutil.TimeoutExpired:
                        proc.kill()
                    killed.append({
                        "pid": p_pid,
                        "name": p_info.get("name"),
                        "cmdline": cmdline[:80]
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return killed


if __name__ == "__main__":
    pm = ProcessManager()
    print("Testing process group launch and graceful SIGTERM...")
    res = pm.launch_process("test_sleep", ["sleep", "10"], process_type="test")
    print(f"Launched: {res}")
    time.sleep(0.5)
    term_res = pm.terminate_process("test_sleep")
    print(f"Terminated: {term_res}")
