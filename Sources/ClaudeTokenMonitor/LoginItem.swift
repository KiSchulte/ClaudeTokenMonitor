import Foundation
import ServiceManagement

/// Autostart über SMAppService. Funktioniert nur mit dem gebauten .app-Bundle,
/// nicht mit dem nackten Binary aus .build/.
enum LoginItem {
    static var isEnabled: Bool {
        SMAppService.mainApp.status == .enabled
    }

    static func statusDescription(_ loc: Loc) -> String {
        switch SMAppService.mainApp.status {
        case .enabled: return loc.loginActive
        case .notRegistered: return loc.loginNotRegistered
        case .requiresApproval: return loc.loginRequiresApproval
        case .notFound: return loc.loginNotFound
        @unknown default: return loc.loginUnknown
        }
    }

    /// Gibt eine Fehlermeldung zurück, wenn das Umschalten fehlschlägt.
    /// Der Text kommt vom System und ist daher systemsprachig.
    @discardableResult
    static func set(_ enabled: Bool) -> String? {
        do {
            if enabled {
                try SMAppService.mainApp.register()
            } else {
                try SMAppService.mainApp.unregister()
            }
            return nil
        } catch {
            return error.localizedDescription
        }
    }
}
