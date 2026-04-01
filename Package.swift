// swift-tools-version: 5.9
// 星图 (XingTu) - 星空座的数据地图
// 风隐 OS 数据元数据系统

import PackageDescription

let package = Package(
    name: "XingTu",
    platforms: [
        .macOS(.v14)
    ],
    products: [
        .library(
            name: "XingTu",
            targets: ["XingTu"]
        ),
        .executable(
            name: "XingTuCLI",
            targets: ["XingTuCLI"]
        ),
        .executable(
            name: "XingTuApp",
            targets: ["XingTuApp"]
        )
    ],
    dependencies: [
        // SQLite.swift - 轻量级 SQLite 封装
        .package(url: "https://github.com/stephencelis/SQLite.swift.git", from: "0.15.0")
    ],
    targets: [
        .target(
            name: "XingTu",
            dependencies: [
                .product(name: "SQLite", package: "SQLite.swift")
            ],
            path: "Sources/XingTu"
        ),
        .executableTarget(
            name: "XingTuCLI",
            dependencies: ["XingTu"],
            path: "Sources/XingTuCLI"
        ),
        .executableTarget(
            name: "XingTuApp",
            dependencies: ["XingTu"],
            path: "Sources/XingTuApp"
        )
    ]
)
