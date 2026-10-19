"""Native macOS status menu; no persistent window, Dock icon or Tk dependency."""
import sys
from pathlib import Path

import AppKit as AK
import Foundation as F
import ServiceManagement as SM
import objc

from companion.app import Settings
from companion.storage import default_data_dir
from .controller import CompanionController
from .extension_files import revealable_extension
from .session import BackgroundSession


class MenuDelegate(F.NSObject, protocols=[objc.protocolNamed("NSApplicationDelegate"), objc.protocolNamed("NSMenuDelegate")]):
    @objc.typedSelector(b"v@:@")
    def applicationDidFinishLaunching_(self, notification):
        self.session = BackgroundSession(CompanionController(Settings(default_data_dir())))
        self.termination_requested = False
        self.status_item = AK.NSStatusBar.systemStatusBar().statusItemWithLength_(AK.NSVariableStatusItemLength)
        self.status_item.button().setTitle_("DK")
        icon_path = Path(getattr(sys, "_MEIPASS", Path(__file__).parents[1])) / "desktop/menu-icon.png"
        icon = AK.NSImage.alloc().initWithContentsOfFile_(str(icon_path))
        if icon:
            icon.setSize_((18, 18))
            icon.setTemplate_(True)
            self.status_item.button().setImage_(icon)
            self.status_item.button().setImagePosition_(AK.NSImageLeft)
        self.status_item.button().setAccessibilityLabel_("draft-kit")
        self.menu = AK.NSMenu.alloc().init()
        self.menu.setAutoenablesItems_(False)
        self.menu.setDelegate_(self)
        self.state_item = self.item("draft-kit · Starting…")
        self.detail_item = self.item("Local address: http://127.0.0.1:1455")
        self.separator()
        self.copy_item = self.item("Copy pairing code", "copyCode:")
        self.restart_item = self.item("New pairing code", "restart:")
        self.toggle_item = self.item("Stop companion", "toggle:")
        self.separator()
        self.item("Setup instructions…", "setup:")
        self.item("Show extension for beta install…", "revealExtension:")
        self.login_item = self.item("Open at login", "toggleLogin:")
        self.demo_item = self.item("Demo mode", "toggleDemo:")
        self.separator()
        self.item("Quit draft-kit", "quit:", "q")
        self.status_item.setMenu_(self.menu)
        self.refresh_login()
        self.timer = F.NSTimer.timerWithTimeInterval_target_selector_userInfo_repeats_(.3, self, "poll:", None, True)
        F.NSRunLoop.mainRunLoop().addTimer_forMode_(self.timer, F.NSRunLoopCommonModes)
        self.session.start()
        self.poll_(None)

    @objc.python_method
    def item(self, title, action=None, shortcut=""):
        item = AK.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, shortcut)
        item.setTarget_(self)
        item.setEnabled_(action is not None)
        self.menu.addItem_(item)
        return item

    @objc.python_method
    def separator(self):
        self.menu.addItem_(AK.NSMenuItem.separatorItem())

    @objc.python_method
    def alert(self, title, text):
        AK.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        alert = AK.NSAlert.alloc().init()
        alert.setMessageText_(title)
        alert.setInformativeText_(text)
        alert.addButtonWithTitle_("OK")
        alert.runModal()

    @objc.IBAction
    def poll_(self, sender):
        ready_to_quit = self.session.poll()
        if ready_to_quit:
            self.timer.invalidate()
            app = AK.NSApplication.sharedApplication()
            if self.termination_requested:
                app.replyToApplicationShouldTerminate_(True)
            else:
                app.terminate_(None)
            return
        controller = self.session.controller
        self.state_item.setTitle_("draft-kit · " + self.session.status)
        self.detail_item.setTitle_(self.session.detail)
        self.status_item.button().setToolTip_("draft-kit · " + self.session.status)
        available = controller.running and not self.session.restart_pending and not self.session.quitting
        self.copy_item.setEnabled_(available)
        self.restart_item.setEnabled_(available)
        self.toggle_item.setTitle_("Stop companion" if controller.busy else "Start companion")
        self.toggle_item.setEnabled_(not self.session.quitting)
        self.demo_item.setState_(AK.NSControlStateValueOn if controller.settings.demo else AK.NSControlStateValueOff)
        self.demo_item.setEnabled_(not self.session.quitting)

    @objc.typedSelector(b"v@:@")
    def menuWillOpen_(self, menu):
        self.refresh_login()
        self.poll_(None)

    @objc.IBAction
    def copyCode_(self, sender):
        controller = self.session.controller
        if controller.running:
            clipboard = AK.NSPasteboard.generalPasteboard()
            clipboard.clearContents()
            clipboard.setString_forType_(controller.pairing_code, AK.NSPasteboardTypeString)

    @objc.IBAction
    def toggle_(self, sender):
        if self.session.controller.busy:
            self.session.stop()
        else:
            self.session.start()
        self.poll_(None)

    @objc.IBAction
    def restart_(self, sender):
        self.session.restart()
        self.poll_(None)

    @objc.IBAction
    def toggleDemo_(self, sender):
        self.session.set_demo(not self.session.controller.settings.demo)
        self.poll_(None)

    @objc.IBAction
    def setup_(self, sender):
        self.alert("Connect draft-kit", "1. Install the Chrome extension and open Connect.\n2. Choose DK → Copy pairing code, then pair.\n3. Continue with ChatGPT.\n4. Upload your résumé or paste your experience.\n\nKeep DK running while writing. Open at login is optional.")

    @objc.IBAction
    def revealExtension_(self, sender):
        try:
            folder = revealable_extension(self.session.controller.settings.data_dir)
            AK.NSWorkspace.sharedWorkspace().openURL_(F.NSURL.fileURLWithPath_(str(folder)))
            self.alert("Install the beta extension", "Open chrome://extensions, enable Developer mode and choose Load unpacked. Select the extension folder that just opened. After updates, click Reload.")
        except Exception:
            self.alert("Extension unavailable", "Download the extension ZIP and follow the beta installation guide.")

    @objc.python_method
    def refresh_login(self):
        # Query the OS rather than pretending a local preference enables login.
        if not getattr(sys, "frozen", False):
            self.login_item.setTitle_("Open at login · install app first")
            self.login_item.setEnabled_(False)
            return
        try:
            status = SM.SMAppService.mainAppService().status()
            needs_approval = status == SM.SMAppServiceStatusRequiresApproval
            self.login_item.setTitle_("Open at login · approval needed…" if needs_approval else "Open at login")
            enabled = status in (SM.SMAppServiceStatusEnabled, SM.SMAppServiceStatusRequiresApproval)
            self.login_item.setState_(AK.NSControlStateValueOn if enabled else AK.NSControlStateValueOff)
            self.login_item.setEnabled_(not self.session.quitting)
        except Exception:
            self.login_item.setTitle_("Open at login · unavailable")
            self.login_item.setEnabled_(False)

    @objc.IBAction
    def toggleLogin_(self, sender):
        try:
            service = SM.SMAppService.mainAppService()
            if service.status() == SM.SMAppServiceStatusRequiresApproval:
                SM.SMAppService.openSystemSettingsLoginItems()
                return
            operation = service.unregisterAndReturnError_ if service.status() == SM.SMAppServiceStatusEnabled else service.registerAndReturnError_
            succeeded, error = operation(None)
            if not succeeded:
                self.alert("Could not change Open at login", "Check System Settings → General → Login Items. Install the app in Applications and try again.")
            elif service.status() == SM.SMAppServiceStatusRequiresApproval:
                SM.SMAppService.openSystemSettingsLoginItems()
        except Exception:
            self.alert("Open at login unavailable", "You can add draft-kit in System Settings → General → Login Items, or open it from Applications when needed.")
        self.refresh_login()

    @objc.IBAction
    def quit_(self, sender):
        self.session.quit()
        self.poll_(None)

    # NSApplicationTerminateReply is NSUInteger on both supported 64-bit Macs.
    # PyObjC's inferred 32-bit return signature fails protocol validation.
    @objc.typedSelector(b"Q@:@")
    def applicationShouldTerminate_(self, sender):
        if not self.session.controller.busy:
            return AK.NSTerminateNow
        self.termination_requested = True
        self.session.quit()
        return AK.NSTerminateLater

    @objc.typedSelector(b"v@:@")
    def applicationWillTerminate_(self, notification):
        self.session.controller.stop()
        self.session.controller.wait()


def main():
    app = AK.NSApplication.sharedApplication()
    app.setActivationPolicy_(AK.NSApplicationActivationPolicyAccessory)
    delegate = MenuDelegate.alloc().init()
    app.setDelegate_(delegate)
    try:
        app.run()
    finally:
        if hasattr(delegate, "session"):
            delegate.session.quit()
            delegate.session.controller.wait()
