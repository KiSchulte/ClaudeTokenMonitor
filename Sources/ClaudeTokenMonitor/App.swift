import AppKit
import SwiftUI

@main
struct ClaudeTokenMonitorApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var delegate
    @ObservedObject private var store = UsageStore.shared

    init() {
        // Textausgabe zum Prüfen der Zahlen ohne GUI:
        //   ClaudeTokenMonitor --dump
        if CommandLine.arguments.contains("--dump") {
            CLIDump.run()
            exit(0)
        }
        // Autostart von der Kommandozeile prüfen/setzen.
        let loc = Loc(language: CLIDump.language())
        if CommandLine.arguments.contains("--login-status") {
            print("\(loc.cliAutostart): \(LoginItem.statusDescription(loc))")
            exit(0)
        }
        if CommandLine.arguments.contains("--register-login") {
            if let error = LoginItem.set(true) {
                print("\(loc.cliError): \(error)")
                exit(1)
            }
            print("\(loc.cliAutostart): \(LoginItem.statusDescription(loc))")
            exit(0)
        }
        if CommandLine.arguments.contains("--unregister-login") {
            if let error = LoginItem.set(false) {
                print("\(loc.cliError): \(error)")
                exit(1)
            }
            print("\(loc.cliAutostart): \(LoginItem.statusDescription(loc))")
            exit(0)
        }
    }

    var body: some Scene {
        MenuBarExtra {
            MainView()
                .environmentObject(store)
        } label: {
            HStack(spacing: 3) {
                Image(systemName: "sparkles")
                Text(store.menuBarText)
                if let secondary = store.menuBarSecondaryText {
                    Text(secondary).foregroundStyle(.secondary)
                }
            }
        }
        .menuBarExtraStyle(.window)
    }
}

/// Öffnet mit `--preview` dieselbe Oberfläche zusätzlich in einem normalen
/// Fenster — praktisch zum Layout-Prüfen und wenn man das Panel offen halten will.
final class AppDelegate: NSObject, NSApplicationDelegate {
    private var window: NSWindow?

    func applicationDidFinishLaunching(_ notification: Notification) {
        guard CommandLine.arguments.contains("--preview") else { return }

        let view = MainView().environmentObject(UsageStore.shared)
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 470, height: 630),
            styleMask: [.titled, .closable, .miniaturizable],
            backing: .buffered,
            defer: false
        )
        window.title = "Claude Token Monitor"
        window.contentView = NSHostingView(rootView: view)
        window.center()
        window.isReleasedWhenClosed = false
        self.window = window

        NSApp.setActivationPolicy(.regular)
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }
}
