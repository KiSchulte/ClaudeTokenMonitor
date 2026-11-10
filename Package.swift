// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "ClaudeTokenMonitor",
    platforms: [.macOS(.v14)],
    targets: [
        .executableTarget(
            name: "ClaudeTokenMonitor",
            path: "Sources/ClaudeTokenMonitor"
        ),
        // Erzeugt das App-Icon beim Build — siehe build.sh.
        .executableTarget(
            name: "IconGen",
            path: "Sources/IconGen"
        ),
    ]
)
