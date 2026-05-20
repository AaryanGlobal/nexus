"""
Nexus Daemon - Background Service for Continuous Operation

Features:
- PID file management
- Auto-restart on crash
- Health monitoring
- Log rotation
- Signal handling (SIGTERM, SIGUSR1)
- Graceful shutdown
"""
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import os
import signal
import time
import threading
import logging
import json
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class DaemonConfig:
    """Configuration for daemon mode."""
    pid_file: str = "/tmp/nexus-daemon.pid"
    log_file: str = "/tmp/nexus-daemon.log"
    state_file: str = "/tmp/nexus-daemon-state.json"
    port: int = 8080
    host: str = "0.0.0.0"
    auto_restart: bool = True
    restart_delay: float = 1.0  # seconds
    max_restarts: int = 3
    check_interval: float = 5.0  # seconds
    max_log_size_mb: float = 10.0
    log_level: str = "INFO"
    
    def __post_init__(self):
        """Validate configuration."""
        if not (1 <= self.port <= 65535):
            raise ValueError(f"Port must be 1-65535, got {self.port}")


@dataclass
class DaemonState:
    """Runtime state of daemon."""
    running: bool = False
    pid: Optional[int] = None
    started_at: Optional[datetime] = None
    restart_count: int = 0
    last_error: Optional[str] = None
    last_check: Optional[datetime] = None
    
    def start(self, pid: int):
        """Record daemon start."""
        self.running = True
        self.pid = pid
        self.started_at = datetime.now()
        self.restart_count += 1
        self.last_error = None
    
    def stop(self):
        """Record daemon stop."""
        self.running = False
        self.pid = None
    
    def record_error(self, error: str):
        """Record an error and increment restart count."""
        self.last_error = error
        self.restart_count += 1
    
    @property
    def uptime_seconds(self) -> float:
        """Calculate uptime in seconds."""
        if not self.started_at:
            return 0
        return (datetime.now() - self.started_at).total_seconds()


class NexusDaemon:
    """
    Background service for Nexus.
    
    Manages:
    - PID file lifecycle
    - Auto-restart on crash
    - Health monitoring
    - Log rotation
    - Signal handling
    """
    
    def __init__(self, config: DaemonConfig | None = None):
        self.config = config or DaemonConfig()
        self.state = DaemonState()
        
        # Server instance
        self._server: Optional[object] = None
        self._server_thread: Optional[threading.Thread] = None
        
        # Health monitoring
        self._health_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Lock for thread safety
        self._lock = threading.RLock()
    
    # === PUBLIC API ===
    
    def start(self) -> bool:
        """Start the daemon."""
        with self._lock:
            # Check if already running
            if self.state.running:
                logger.warning("Daemon already running")
                return True
            
            # Check for stale PID
            existing_pid = self._read_pid_file(self.config.pid_file)
            if existing_pid and self._is_process_running(existing_pid):
                logger.error(f"Daemon already running with PID {existing_pid}")
                return False
            
            try:
                # Start the server
                if not self._start_server():
                    raise RuntimeError("Failed to start server")
                
                # Write PID file
                pid = os.getpid()
                self.state.start(pid=pid)
                self._write_pid_file()
                
                # Save state
                self._save_state()
                
                # Start health monitor
                self._running = True
                self._health_thread = threading.Thread(target=self._health_loop, daemon=True)
                self._health_thread.start()
                
                logger.info(f"Daemon started with PID {pid}")
                return True
                
            except Exception as e:
                self.state.record_error(str(e))
                logger.error(f"Failed to start daemon: {e}")
                return False
    
    def stop(self) -> bool:
        """Stop the daemon gracefully."""
        with self._lock:
            if not self.state.running:
                logger.info("Daemon not running")
                return True
            
            try:
                logger.info("Stopping daemon...")
                
                # Stop health monitor
                self._running = False
                if self._health_thread:
                    self._health_thread.join(timeout=2)
                
                # Stop server
                self._stop_server()
                
                # Remove PID file
                self._remove_pid_file()
                
                # Update state
                self.state.stop()
                self._save_state()
                
                logger.info("Daemon stopped")
                return True
                
            except Exception as e:
                logger.error(f"Error stopping daemon: {e}")
                return False
    
    def restart(self) -> bool:
        """Restart the daemon."""
        logger.info("Restarting daemon...")
        
        self.stop()
        time.sleep(self.config.restart_delay)
        
        return self.start()
    
    def get_status(self) -> dict:
        """Get comprehensive daemon status."""
        return {
            'running': self.state.running,
            'pid': self.state.pid,
            'uptime_seconds': self.state.uptime_seconds,
            'restart_count': self.state.restart_count,
            'last_error': self.state.last_error,
            'config': {
                'port': self.config.port,
                'host': self.config.host,
                'auto_restart': self.config.auto_restart,
                'log_file': self.config.log_file,
            }
        }
    
    def get_health(self) -> dict:
        """Get daemon health metrics."""
        health = {
            'running': self.state.running,
            'pid': self.state.pid,
            'uptime': self.state.uptime_seconds,
            'restart_count': self.state.restart_count,
            'healthy': True,
        }
        
        try:
            import psutil
            
            # Memory usage
            process = psutil.Process(self.state.pid)
            mem_info = process.memory_info()
            health['memory_mb'] = mem_info.rss / 1024 / 1024
            
            # CPU usage
            health['cpu_percent'] = process.cpu_percent(interval=0.1)
            
            # Check if too many restarts
            if self.state.restart_count > self.config.max_restarts:
                health['healthy'] = False
                health['unhealthy_reason'] = "Too many restarts"
                
        except ImportError:
            # psutil not installed
            health['memory_mb'] = 'N/A'
            health['cpu_percent'] = 'N/A'
        except Exception as e:
            health['healthy'] = False
            health['error'] = str(e)
        
        return health
    
    def handle_signal(self, sig, frame=None) -> bool:
        """Handle system signals."""
        if sig == signal.SIGTERM:
            logger.info("Received SIGTERM")
            self.stop()
            return True
        
        elif sig == signal.SIGUSR1:
            logger.info("Received SIGUSR1, reloading config...")
            self._reload_config()
            return True
        
        return False
    
    # === SERVER MANAGEMENT ===
    
    def _start_server(self) -> bool:
        """Start the HTTP server."""
        try:
            from hermes_pi_bridge_core.nexus_server import NexusServer
            
            self._server = NexusServer(
                host=self.config.host,
                port=self.config.port
            )
            
            # Start server in background thread
            self._server_thread = threading.Thread(
                target=self._server.serve_forever,
                daemon=True
            )
            self._server_thread.start()
            
            # Wait briefly for server to start
            time.sleep(0.1)
            
            return True
            
        except Exception as e:
            logger.error(f"Server start failed: {e}")
            return False
    
    def _stop_server(self):
        """Stop the HTTP server."""
        if self._server:
            try:
                self._server.shutdown()
            except Exception as e:
                logger.warning(f"Error stopping server: {e}")
            self._server = None
    
    # === HEALTH MONITORING ===
    
    def _health_loop(self):
        """Background health monitoring loop."""
        while self._running:
            try:
                self._perform_health_check()
            except Exception as e:
                logger.error(f"Health check error: {e}")
            
            time.sleep(self.config.check_interval)
    
    def _perform_health_check(self):
        """Perform a single health check."""
        self.state.last_check = datetime.now()
        
        # Check if server is responding
        if self._server:
            try:
                # Server should expose health endpoint
                if hasattr(self._server, 'is_healthy'):
                    if not self._server.is_healthy():
                        logger.warning("Server health check failed")
                        self._handle_unhealthy()
            except Exception:
                pass
        
        # Check process is alive
        if self.state.pid and not self._is_process_running(self.state.pid):
            logger.error("Daemon process died")
            self._handle_crash()
    
    def _handle_unhealthy(self):
        """Handle unhealthy daemon."""
        if self.config.auto_restart:
            logger.info("Attempting auto-restart...")
            self.restart()
    
    def _handle_crash(self):
        """Handle daemon crash."""
        self.state.record_error("Process died unexpectedly")
        
        if self.config.auto_restart and self.state.restart_count < self.config.max_restarts:
            logger.info(f"Auto-restarting (attempt {self.state.restart_count})")
            time.sleep(self.config.restart_delay)
            self.start()
        else:
            logger.error("Auto-restart disabled or max restarts reached")
            self._remove_pid_file()
    
    # === PID FILE MANAGEMENT ===
    
    def _write_pid_file(self):
        """Write PID to file."""
        path = Path(self.config.pid_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(os.getpid()))
        path.chmod(0o644)
    
    def _remove_pid_file(self):
        """Remove PID file."""
        try:
            Path(self.config.pid_file).unlink(missing_ok=True)
        except Exception:
            pass
    
    @staticmethod
    def _read_pid_file(pid_file: str) -> int | None:
        """Read PID from file."""
        try:
            path = Path(pid_file)
            if path.exists():
                return int(path.read_text().strip())
        except Exception:
            pass
        return None
    
    @staticmethod
    def _is_process_running(pid: int) -> bool:
        """Check if process is running."""
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False
    
    # === STATE PERSISTENCE ===
    
    def _save_state(self):
        """Save daemon state to disk."""
        try:
            path = Path(self.config.state_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            state = {
                'running': self.state.running,
                'pid': self.state.pid,
                'started_at': self.state.started_at.isoformat() if self.state.started_at else None,
                'restart_count': self.state.restart_count,
                'last_error': self.state.last_error,
            }
            
            path.write_text(json.dumps(state, indent=2))
            
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    def _load_state(self):
        """Load daemon state from disk."""
        try:
            path = Path(self.config.state_file)
            if path.exists():
                state = json.loads(path.read_text())
                self.state.pid = state.get('pid')
                self.state.restart_count = state.get('restart_count', 0)
                
                if state.get('started_at'):
                    self.state.started_at = datetime.fromisoformat(state['started_at'])
                    
        except Exception as e:
            logger.warning(f"Failed to load state: {e}")
    
    # === LOGGING ===
    
    def _write_log(self, message: str, level: str = "INFO"):
        """Write to log file."""
        try:
            if level == "DEBUG" and self.config.log_level != "DEBUG":
                return
            
            path = Path(self.config.log_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Check log rotation
            if path.exists() and path.stat().st_size > self.config.max_log_size_mb * 1024 * 1024:
                # Rotate log
                backup = path.with_suffix('.old')
                path.rename(backup)
            
            # Append log
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(path, 'a') as f:
                f.write(f"[{timestamp}] [{level}] {message}\n")
                
        except Exception as e:
            logger.warning(f"Failed to write log: {e}")
    
    # === CONFIG MANAGEMENT ===
    
    def _reload_config(self):
        """Reload configuration."""
        # In production, would reload from file/env
        logger.info("Config reload not fully implemented")
    
    def register_signal_handlers(self):
        """Register signal handlers for graceful shutdown."""
        signal.signal(signal.SIGTERM, self.handle_signal)
        signal.signal(signal.SIGUSR1, self.handle_signal)


# Singleton
_daemon: Optional[NexusDaemon] = None


def get_daemon(config: DaemonConfig | None = None) -> NexusDaemon:
    """Get singleton daemon instance."""
    global _daemon
    if _daemon is None:
        _daemon = NexusDaemon(config)
    return _daemon


def run_daemon(config: DaemonConfig | None = None) -> int:
    """Run daemon and return exit code."""
    daemon = get_daemon(config)
    daemon.register_signal_handlers()
    
    if daemon.start():
        logger.info("Daemon running, press Ctrl+C to stop")
        
        try:
            while daemon.state.running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Interrupted")
    
    return 0