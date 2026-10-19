"""Background lifecycle shared by the native menu and runtime checks."""


class BackgroundSession:
    def __init__(self, controller):
        self.controller = controller
        self.restart_pending = False
        self.quitting = False
        self.error = ""

    def start(self):
        if self.quitting:
            return
        self.error = ""
        try:
            self.controller.start()
        except RuntimeError as error:
            self.error = str(error)
        except Exception:
            self.error = "Could not open protected storage. Check your OS credential store and try again."

    def stop(self):
        self.restart_pending = False
        self.controller.stop()

    def restart(self):
        if not self.quitting:
            self.restart_pending = True
            self.controller.stop()

    def set_demo(self, enabled):
        self.controller.settings.demo = bool(enabled)
        self.restart()

    def quit(self):
        self.quitting = True
        self.stop()

    def poll(self):
        if self.restart_pending and not self.controller.busy and not self.quitting:
            self.restart_pending = False
            self.start()
        return self.quitting and not self.controller.busy

    @property
    def status(self):
        if self.quitting:
            return "Stopping…"
        if self.restart_pending:
            return "Restarting…"
        if self.controller.running:
            return "Running · Demo" if self.controller.settings.demo else "Running"
        if self.controller.busy:
            return "Starting or stopping…"
        return "Stopped"

    @property
    def detail(self):
        return self.error or self.controller.error or f"Local address: http://127.0.0.1:{self.controller.settings.port}"
