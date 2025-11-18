"""
SOLLOL Integration for NERVA

Provides unified dashboard integration:
- Auto-launches SOLLOL dashboard when NERVA starts
- Registers NERVA as an application in the dashboard
- Sends periodic heartbeats to stay visible
- Provides clean shutdown/unregistration
"""

import atexit
import logging
import os
import subprocess
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Optional imports - gracefully handle if SOLLOL not installed
try:
    from sollol.dashboard_launcher import DashboardProcessLauncher
    from sollol.dashboard_client import DashboardClient
    SOLLOL_AVAILABLE = True
except ImportError:
    SOLLOL_AVAILABLE = False
    DashboardProcessLauncher = None
    DashboardClient = None


class NERVADashboardIntegration:
    """
    Manages SOLLOL dashboard integration for NERVA.

    Features:
    - Auto-launches SOLLOL unified dashboard on first NERVA instance
    - Registers NERVA as an application for observability
    - Automatic heartbeats and graceful cleanup
    """

    def __init__(
        self,
        app_name: str = "NERVA",
        dashboard_port: int = 8080,
        gateway_port: int = 8000,
        redis_url: str = "redis://localhost:6379",
        auto_launch_dashboard: bool = True,
        auto_launch_gateway: bool = True,
        auto_register: bool = True,
    ):
        """
        Initialize SOLLOL dashboard integration.

        Args:
            app_name: Name to display in dashboard
            dashboard_port: Port for SOLLOL dashboard (default: 8080)
            gateway_port: Port for SOLLOL gateway router (default: 8000)
            redis_url: Redis URL for dashboard communication
            auto_launch_dashboard: Automatically launch dashboard if not running
            auto_launch_gateway: Automatically launch gateway router if not running
            auto_register: Automatically register NERVA with dashboard
        """
        self.app_name = app_name
        self.dashboard_port = dashboard_port
        self.gateway_port = gateway_port
        self.redis_url = redis_url
        self.dashboard_url = f"http://localhost:{dashboard_port}"
        self.gateway_url = f"http://localhost:{gateway_port}"

        self.dashboard_launcher: Optional[DashboardProcessLauncher] = None
        self.dashboard_client: Optional[DashboardClient] = None
        self.gateway_process: Optional[subprocess.Popen] = None
        self._dashboard_launched_by_us = False
        self._gateway_launched_by_us = False

        if not SOLLOL_AVAILABLE:
            logger.warning(
                "SOLLOL not installed. Dashboard integration disabled. "
                "Install with: pip install -e ~/SOLLOL"
            )
            return

        # Launch gateway if requested
        if auto_launch_gateway:
            self._launch_gateway()

        # Launch dashboard if requested
        if auto_launch_dashboard:
            self._launch_dashboard()

        # Register with dashboard
        if auto_register:
            self._register()

        # Register cleanup on exit
        atexit.register(self.cleanup)

    def _launch_gateway(self) -> bool:
        """
        Launch SOLLOL gateway router if not already running.

        Returns:
            True if gateway is running (either already or newly launched)
        """
        if not SOLLOL_AVAILABLE:
            return False

        # Check if gateway is already running
        if self._is_gateway_running():
            logger.info(f"✅ SOLLOL Gateway already running at {self.gateway_url}")
            return True

        # Launch new gateway instance via subprocess
        try:
            logger.info(f"🚀 Launching SOLLOL Gateway on port {self.gateway_port}...")

            # Use subprocess to run sollol up in the background
            self.gateway_process = subprocess.Popen(
                ["sollol", "up", "--port", str(self.gateway_port)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,  # Detach from parent process
            )

            # Wait a moment for it to start
            time.sleep(2)

            # Verify it started
            if self._is_gateway_running():
                self._gateway_launched_by_us = True
                print(f"\n✅ SOLLOL Gateway launched at {self.gateway_url}")
                print(f"   🔀 LLM requests will be routed through SOLLOL")
                print()
                return True
            else:
                logger.error("SOLLOL Gateway failed to start")
                return False

        except Exception as e:
            logger.error(f"Error launching gateway: {e}")
            return False

    def _is_gateway_running(self) -> bool:
        """
        Check if SOLLOL gateway is already running.

        Returns:
            True if gateway is accessible
        """
        if not SOLLOL_AVAILABLE:
            return False

        try:
            import requests
            # Check root endpoint which returns service info
            response = requests.get(f"{self.gateway_url}/", timeout=2)
            if response.ok:
                data = response.json()
                return data.get("service") == "SOLLOL"
            return False
        except Exception:
            return False

    def _launch_dashboard(self) -> bool:
        """
        Launch SOLLOL unified dashboard if not already running.

        Returns:
            True if dashboard is running (either already or newly launched)
        """
        if not SOLLOL_AVAILABLE:
            return False

        # Check if dashboard is already running
        if self._is_dashboard_running():
            logger.info(f"✅ SOLLOL Dashboard already running at {self.dashboard_url}")
            return True

        # Launch new dashboard instance
        try:
            logger.info(f"🚀 Launching SOLLOL Unified Dashboard on port {self.dashboard_port}...")

            self.dashboard_launcher = DashboardProcessLauncher(
                redis_url=self.redis_url,
                port=self.dashboard_port,
                ray_dashboard_port=8265,
                dask_dashboard_port=8787,
                enable_dask=True,
                debug=False,
            )

            success = self.dashboard_launcher.start(background=True)

            if success:
                self._dashboard_launched_by_us = True
                print(f"\n✅ SOLLOL Dashboard launched at {self.dashboard_url}")
                print(f"   📊 Open in browser to see NERVA status and logs")
                print()
                return True
            else:
                logger.error("Failed to launch SOLLOL dashboard")
                return False

        except Exception as e:
            logger.error(f"Error launching dashboard: {e}")
            return False

    def _is_dashboard_running(self) -> bool:
        """
        Check if SOLLOL dashboard is already running.

        Returns:
            True if dashboard is accessible
        """
        if not SOLLOL_AVAILABLE:
            return False

        try:
            import requests
            response = requests.get(f"{self.dashboard_url}/health", timeout=2)
            return response.ok
        except Exception:
            return False

    def _register(self) -> bool:
        """
        Register NERVA with SOLLOL dashboard.

        Returns:
            True if registration successful
        """
        if not SOLLOL_AVAILABLE:
            return False

        try:
            self.dashboard_client = DashboardClient(
                app_name=self.app_name,
                router_type="Local Chat Assistant",
                version="0.1.0",
                dashboard_url=self.dashboard_url,
                heartbeat_interval=10,
                metadata={
                    "type": "chat_assistant",
                    "features": ["text-to-speech", "conversation", "memory"],
                    "llm_backend": "Ollama",
                },
                auto_register=True,
            )

            logger.info(f"✅ Registered {self.app_name} with SOLLOL dashboard")
            return True

        except Exception as e:
            logger.warning(f"Could not register with dashboard: {e}")
            return False

    def update_status(self, **metadata):
        """
        Update NERVA's status in the dashboard.

        Args:
            **metadata: Key-value pairs to update in dashboard
        """
        if self.dashboard_client:
            self.dashboard_client.update_metadata(metadata)

    def cleanup(self):
        """
        Clean up dashboard integration on shutdown.

        Unregisters from dashboard but does NOT stop the dashboard/gateway
        (they may be used by other applications).
        """
        if self.dashboard_client:
            try:
                self.dashboard_client.unregister()
                logger.info("✅ Unregistered from SOLLOL dashboard")
            except Exception as e:
                logger.debug(f"Error during unregister: {e}")

        # Leave gateway and dashboard running for other apps
        # User can manually stop with:
        # - Gateway: sollol down
        # - Dashboard: pkill -f "sollol.dashboard_service"
        if self._gateway_launched_by_us:
            logger.info("🔀 SOLLOL Gateway left running for other applications")
        if self._dashboard_launched_by_us and self.dashboard_launcher:
            logger.info("📊 SOLLOL Dashboard left running for other applications")

    def get_dashboard_url(self) -> Optional[str]:
        """
        Get the URL of the SOLLOL dashboard.

        Returns:
            Dashboard URL if available, None otherwise
        """
        if self._is_dashboard_running():
            return self.dashboard_url
        return None


# Global singleton instance
_dashboard_integration: Optional[NERVADashboardIntegration] = None


def get_dashboard_integration(
    auto_launch: bool = True,
    auto_register: bool = True,
) -> Optional[NERVADashboardIntegration]:
    """
    Get or create the global SOLLOL dashboard integration instance.

    Args:
        auto_launch: Launch dashboard if not running
        auto_register: Register NERVA with dashboard

    Returns:
        NERVADashboardIntegration instance or None if SOLLOL not available
    """
    global _dashboard_integration

    if not SOLLOL_AVAILABLE:
        return None

    if _dashboard_integration is None:
        _dashboard_integration = NERVADashboardIntegration(
            auto_launch_dashboard=auto_launch,
            auto_register=auto_register,
        )

    return _dashboard_integration


def disable_dashboard_integration():
    """
    Disable dashboard integration (useful for testing or --no-dashboard flag).
    """
    global _dashboard_integration
    if _dashboard_integration:
        _dashboard_integration.cleanup()
        _dashboard_integration = None
