import rumps
import os
import sys
import logging
import subprocess
import threading

from PyObjCTools import AppHelper

logger = logging.getLogger(__name__)

# Grace period after starting xmrig during which we poll for an immediate
# crash. Anything that exits inside this window almost certainly has a config
# or permission problem we want to surface, not hide behind a "running" menu
# state. Matches the original 0.25s sleep.
STARTUP_GRACE_SECONDS = 0.25
STARTUP_CHECK_INTERVAL = 0.05

# Timeouts used when stopping xmrig for shutdown paths (quit, exception
# handler) where the user is waiting on the app to exit. Kept short so the
# total wait stays well under macOS's 5s unresponsiveness threshold for a
# blocking main-thread Quit handler.
SHUTDOWN_SIGTERM_TIMEOUT = 1
SHUTDOWN_SIGKILL_TIMEOUT = 0.5

# Timeouts used for the user-facing toggle path. A bit more generous so a
# well-behaved xmrig can wind down its workers cleanly.
TOGGLE_SIGTERM_TIMEOUT = 3
TOGGLE_SIGKILL_TIMEOUT = 2


def init(filename="xmmanager.log"):
    logging.basicConfig(filename=filename, level=logging.INFO)
    logger.info("Initialized logger")


def find_xmrig():
    """Locate the xmrig binary on disk. Returns an absolute path or None.

    GUI apps launched by Launch Services on macOS inherit a stripped $PATH
    (just /usr/bin:/bin:/usr/sbin:/sbin), so the standard "which" approach
    won't see Homebrew, MacPorts, or user bin dirs. We check a fixed list
    of common install locations instead.

    Search order:
      1. $XMRIG_PATH env var (explicit override)
      2. Homebrew Apple Silicon: /opt/homebrew/bin/xmrig
      3. Homebrew Intel:         /usr/local/bin/xmrig
      4. MacPorts:               /opt/local/bin/xmrig
      5. User bin dirs:          ~/bin/xmrig, ~/.local/bin/xmrig
      6. Adjacent to the .app    (legacy "same folder" install)
      7. Next to main.py         (dev fallback when running from source)
    """
    def _is_xmrig(path):
        return (
            path
            and os.path.isfile(path)
            and os.access(path, os.X_OK)
        )

    # 1. Explicit env override wins.
    env = os.environ.get("XMRIG_PATH")
    if _is_xmrig(env):
        logger.info(f"Using xmrig from XMRIG_PATH: {env}")
        return env

    # 2-4. Homebrew and MacPorts.
    for path in (
        "/opt/homebrew/bin/xmrig",
        "/usr/local/bin/xmrig",
        "/opt/local/bin/xmrig",
    ):
        if _is_xmrig(path):
            logger.info(f"Found xmrig at {path}")
            return path

    # 5. User bin dirs.
    home = os.path.expanduser("~")
    for path in (
        os.path.join(home, "bin", "xmrig"),
        os.path.join(home, ".local", "bin", "xmrig"),
    ):
        if _is_xmrig(path):
            logger.info(f"Found xmrig at {path}")
            return path

    # 6. Legacy: xmrig sitting next to XMManager.app in the same folder.
    if getattr(sys, "frozen", False):
        bundle = os.path.dirname(
            os.path.dirname(os.path.dirname(sys.executable))
        )
        adjacent = os.path.join(os.path.dirname(bundle), "xmrig")
        if _is_xmrig(adjacent):
            logger.info(f"Found xmrig at {adjacent}")
            return adjacent

    # 7. Dev fallback when running from source.
    if not getattr(sys, "frozen", False):
        dev_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "xmrig"
        )
        if _is_xmrig(dev_path):
            logger.info(f"Found xmrig at {dev_path}")
            return dev_path

    logger.error(
        "xmrig not found in any standard location. Install via "
        "`brew install xmrig` or set the XMRIG_PATH environment variable."
    )
    return None


class Main(rumps.App):
    def __init__(self, *args, xmrig_path=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Resolved path to the xmrig binary, or None if it could not be
        # located anywhere. The Main.__init__ caller (see __main__) is
        # responsible for searching; we just store the result.
        self.xmrig_path = xmrig_path
        self.xmrig_command = (
            [xmrig_path, "--cpu-priority=0"] if xmrig_path else None
        )
        # Popen handle for the running xmrig, or None when stopped.
        # Source of truth for the toggle state.
        self.xmrig_process = None
        # rumps.Timer used to poll xmrig during the startup grace window.
        # Reused across restarts; we always stop() before start() to avoid
        # leaking NSTimers into the run loop.
        self._startup_check_timer = rumps.Timer(
            self._check_xmrig_startup, STARTUP_CHECK_INTERVAL
        )
        # Counter of remaining seconds (in check-interval units) the grace
        # timer should keep firing for the most recent start.
        self._grace_remaining = 0
        # Handle the grace timer was last armed for. Used by the callback
        # to detect that the user has already taken action (reconciled a
        # crash, or started a new process) so the timer does not double-
        # notify or clobber a fresh toggle state.
        self._grace_target = None

        # If xmrig was not found at startup, schedule a one-shot quit
        # notification. We can't call rumps.notification + quit_application
        # from __init__ because the NSApp run loop hasn't started yet, so
        # the notification would be dropped and terminate_() would target
        # an unstarted app. The timer fires once the run loop is alive.
        self._missing_quit_timer = rumps.Timer(
            self._handle_missing_xmrig, 0.1
        )

    @rumps.clicked("Toggle XMRig")
    def mining_controller(self, sender):
        # Reconcile stale menu state. rumps does NOT auto-toggle a checkmark
        # on click, so if xmrig died unexpectedly the checkmark can lie.
        # Trust process reality over the menu state, but only flip the menu
        # back when we are sure the user did not just click "stop".
        if sender.state and not self._is_running():
            logger.warning("Toggle was checked but xmrig is not running; reconciling")
            # Clear the dead handle and cancel the grace timer so its
            # pending tick (if any) does not double-notify the user.
            self.xmrig_process = None
            self._startup_check_timer.stop()
            self._grace_target = None
            rumps.notification(
                "XMManager",
                "XMRig stopped unexpectedly",
                "Check xmmanager.log for details.",
            )
            self._set_toggle_state(False)
            return

        if self._is_running():
            self._stop_xmrig_async()
            # Leave the checkmark visible during the brief cleanup window so
            # the menu does not flicker. The background thread will clear it
            # via AppHelper.callAfter once the process is actually gone.
            return

        if self._start_xmrig():
            self._set_toggle_state(True)
        else:
            self._set_toggle_state(False)
            rumps.notification(
                "XMManager",
                "Failed to start XMRig",
                "Check xmmanager.log for details.",
            )

    @rumps.clicked("Quit")
    def on_quit(self, _):
        # Synchronous shutdown. A daemon background thread would be killed
        # by the Python interpreter during Cocoa app teardown, leaving
        # xmrig running as an orphan. We accept a short blocking wait on
        # the main thread so SIGTERM/SIGKILL actually land before the app
        # exits. SHUTDOWN_* timeouts keep the total under ~1.5s.
        try:
            self._stop_xmrig_sync(
                sigterm_timeout=SHUTDOWN_SIGTERM_TIMEOUT,
                sigkill_timeout=SHUTDOWN_SIGKILL_TIMEOUT,
            )
        except Exception as e:
            logger.error(f"Error stopping xmrig on quit: {e}")
        logger.info("Exiting...")
        rumps.quit_application()

    def run(self, *args, **kwargs):
        # If xmrig was not found at startup, fire the missing-quit timer
        # so it can post a notification and exit the app cleanly. Started
        # here (not in __init__) because the NSApp run loop has to be
        # running before NSTimers can be scheduled against it.
        if self.xmrig_path is None:
            self._missing_quit_timer.start()
        super().run(*args, **kwargs)

    def _handle_missing_xmrig(self, _timer):
        """One-shot callback: tell the user xmrig is missing, then exit.

        Fires from a rumps.Timer started in run() (not __init__) so the
        NSApp run loop is already up. The timer is repeating under the
        hood, so we stop it before doing anything to guarantee this is
        actually one-shot.
        """
        self._missing_quit_timer.stop()
        rumps.notification(
            "XMManager",
            "XMRig not found",
            "Install with `brew install xmrig`, or set the XMRIG_PATH "
            "environment variable to the binary location. See the README.",
        )
        rumps.quit_application()

    def _is_running(self):
        proc = self.xmrig_process
        return proc is not None and proc.poll() is None

    def _set_toggle_state(self, new_state):
        """Set the checkmark on the toggle menu item.

        Must be called on the main thread. Current call sites all satisfy
        that: rumps click handlers run on the main run loop, the grace
        timer's callback fires on the main run loop, and the background
        _stop_xmrig_async thread hops back here via AppHelper.callAfter
        before calling this method.
        """
        # self.menu is a dict-like view of the NSMenu built at run() time.
        # Look up the item by title so timer / background-thread callbacks
        # can update state without a sender reference.
        self.menu["Toggle XMRig"].state = new_state

    def _start_xmrig(self):
        """Start xmrig. Returns True once Popen succeeds and the grace
        timer has been armed. The grace timer is responsible for detecting
        an immediate crash and reverting the toggle state."""
        # Defensive: should be impossible because the app quits via the
        # missing-quit timer when xmrig_path is None, but guard anyway so
        # a stray click can't crash the process with a TypeError.
        if self.xmrig_command is None:
            logger.error("Cannot start xmrig: binary path not resolved")
            return False
        if self._is_running():
            return True
        try:
            self.xmrig_process = subprocess.Popen(
                self.xmrig_command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                # Put xmrig in its own process group so signals we receive
                # on the menu bar app don't leak into the child.
                start_new_session=True,
            )
        except OSError as e:
            logger.error(f"Error starting xmrig: {e}")
            self.xmrig_process = None
            return False

        # Arm the grace timer. Runs on the main run loop, so it is safe to
        # touch menu state from the callback without thread-safe dispatch.
        self._grace_target = self.xmrig_process
        self._grace_remaining = STARTUP_GRACE_SECONDS
        self._startup_check_timer.stop()
        self._startup_check_timer.start()

        logger.info("Started XMRig")
        return True

    def _check_xmrig_startup(self, _timer):
        """Timer callback fired on the main run loop during the startup
        grace window. If xmrig died before the window expired, revert the
        toggle state so the menu does not lie about whether mining is on."""
        # If the process we were watching is no longer the live one, the
        # user has already acted (reconciled a crash, or started a fresh
        # process) — bail so we don't double-notify or clobber the new
        # toggle state. Also covers the case where the process was
        # stopped before the grace window elapsed.
        if self._grace_target is not self.xmrig_process:
            self._startup_check_timer.stop()
            return

        # Crashed early? Revert the toggle so the UI matches reality.
        # Checked before the grace-expiry branch so a crash on the final
        # tick is not silently swallowed by the time-up early return.
        if self.xmrig_process.poll() is not None:
            rc = self.xmrig_process.returncode
            logger.error(f"xmrig exited immediately with code {rc}")
            self.xmrig_process = None
            self._startup_check_timer.stop()
            self._set_toggle_state(False)
            rumps.notification(
                "XMManager",
                "XMRig stopped unexpectedly",
                f"Exited with code {rc}. Check xmmanager.log for details.",
            )
            return

        # Time's up: xmrig survived the grace window, treat it as running.
        self._grace_remaining -= STARTUP_CHECK_INTERVAL
        if self._grace_remaining <= 0:
            self._startup_check_timer.stop()

    def _stop_xmrig_async(self):
        """Stop xmrig on a background thread. Safe to call from main-thread
        callbacks (rumps click handlers) because the actual terminate/wait/
        kill can take up to ~5s and we must not block the macOS main run
        loop. Quit uses _stop_xmrig_sync instead because the interpreter
        kills daemon threads during shutdown."""
        proc = self.xmrig_process
        if proc is None or proc.poll() is not None:
            self.xmrig_process = None
            return

        # Cancel the grace timer. If the user stops during the startup
        # window, the timer would otherwise fire on the next tick, see the
        # process exiting via SIGTERM, and post a spurious "XMRig stopped
        # unexpectedly" notification.
        self._startup_check_timer.stop()

        # Snapshot the handle so a subsequent start (e.g. user toggles back
        # on before cleanup finishes) cannot race with this thread.
        target = proc

        def _shutdown():
            try:
                target.terminate()
                try:
                    target.wait(timeout=TOGGLE_SIGTERM_TIMEOUT)
                except subprocess.TimeoutExpired:
                    logger.warning("xmrig did not exit after SIGTERM, sending SIGKILL")
                    target.kill()
                    target.wait(timeout=TOGGLE_SIGKILL_TIMEOUT)
            except (OSError, ProcessLookupError, subprocess.TimeoutExpired) as e:
                logger.error(f"Error stopping xmrig: {e}")
            finally:
                # Only clear the live handle and update the menu if xmrig
                # is still the one we were stopping. A restart in the
                # meantime would have replaced self.xmrig_process with a
                # new Popen and the new Popen already owns the UI state
                # — flipping the checkmark here would lie about it.
                if self.xmrig_process is target:
                    self.xmrig_process = None
                    # Hop back to the main thread for the menu update.
                    AppHelper.callAfter(self._set_toggle_state, False)
                    logger.info("Stopped XMRig")
                else:
                    logger.info(
                        f"Skipping UI update for stopped xmrig (pid {target.pid}); "
                        f"a new process has taken its place"
                    )

        threading.Thread(target=_shutdown, daemon=True).start()

    def _stop_xmrig_sync(self, sigterm_timeout, sigkill_timeout):
        """Synchronous stop for shutdown paths (exception handler) where
        we are about to os._exit anyway and want a best-effort clean
        termination first."""
        proc = self.xmrig_process
        if proc is None or proc.poll() is not None:
            self.xmrig_process = None
            return
        try:
            proc.terminate()
            try:
                proc.wait(timeout=sigterm_timeout)
            except subprocess.TimeoutExpired:
                logger.warning("xmrig did not exit after SIGTERM, sending SIGKILL")
                proc.kill()
                proc.wait(timeout=sigkill_timeout)
        except (OSError, ProcessLookupError, subprocess.TimeoutExpired) as e:
            logger.error(f"Error stopping xmrig: {e}")
        finally:
            self.xmrig_process = None
        logger.info("Stopped XMRig")


if __name__ == "__main__":
    main_app = None
    try:
        init()
        # Resolve xmrig once at startup. If the binary is missing, Main
        # will show a notification and call rumps.quit_application() from
        # a timer started inside run() — no special-casing needed here.
        xmrig = find_xmrig()
        main_app = Main("XMManager", xmrig_path=xmrig, quit_button=None)
        main_app.run()
    except Exception as e:
        logger.exception(f"Exception: {e}")
        if main_app is not None:
            try:
                main_app._stop_xmrig_sync(
                    sigterm_timeout=SHUTDOWN_SIGTERM_TIMEOUT,
                    sigkill_timeout=SHUTDOWN_SIGKILL_TIMEOUT,
                )
            except Exception as stop_err:
                # Never let a stop failure prevent the force-exit; an
                # orphaned xmrig is the lesser evil compared to a
                # process that won't quit at all.
                logger.error(f"Error stopping xmrig in __main__ handler: {stop_err}")
        logger.info("Force exiting...")
        os._exit(0)
