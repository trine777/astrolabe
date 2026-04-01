// 星图 (XingTu) - 正式应用入口
// 风隐 OS 数据元数据系统

import SwiftUI
import XingTu

@main
struct XingTuApp: App {
    @StateObject private var appState = AppState()
    
    var body: some Scene {
        WindowGroup {
            MainView()
                .environmentObject(appState)
                .preferredColorScheme(.dark)
        }
        .defaultSize(width: 1200, height: 800)
        .commands {
            CommandGroup(replacing: .newItem) {
                Button("导入 CSV...") {
                    appState.showImportSheet = true
                }
                .keyboardShortcut("i", modifiers: .command)
            }
        }
    }
}

// MARK: - 应用状态

@MainActor
class AppState: ObservableObject {
    // 服务
    let service: XingTuService
    
    // UI 状态
    @Published var selectedObjectId: UUID?
    @Published var sidebarSelection: SidebarItem = .allObjects
    @Published var showImportSheet = false
    @Published var isLoading = false
    @Published var errorMessage: String?
    
    // 数据
    @Published var objects: [MetaObject] = []
    @Published var recentEvents: [MetaEvent] = []
    
    enum SidebarItem: String, CaseIterable {
        case allObjects = "所有数据源"
        case drafts = "待确认"
        case confirmed = "已确认"
        case published = "已发布"
        case worldModel = "世界模型"
        case events = "变更记录"
        
        var icon: String {
            switch self {
            case .allObjects: return "cylinder.split.1x2"
            case .drafts: return "doc.badge.clock"
            case .confirmed: return "checkmark.circle"
            case .published: return "arrow.up.circle"
            case .worldModel: return "globe"
            case .events: return "clock.arrow.circlepath"
            }
        }
    }
    
    init() {
        self.service = XingTuService()
        
        Task {
            await initialize()
        }
    }
    
    func initialize() async {
        do {
            try await service.initialize()
            await refreshData()
        } catch {
            errorMessage = error.localizedDescription
        }
    }
    
    func refreshData() async {
        isLoading = true
        defer { isLoading = false }
        
        do {
            objects = try await service.listObjects()
            
            // 获取最近事件
            let filter = EventFilter(since: Calendar.current.date(byAdding: .day, value: -7, to: Date()))
            recentEvents = try await service.eventStream.getHistory(filter: filter, limit: 50)
        } catch {
            errorMessage = error.localizedDescription
        }
    }
    
    func importCSV(url: URL) async throws -> ImportResult {
        isLoading = true
        defer { isLoading = false }
        
        let result = try await service.importCSV(url: url)
        await refreshData()
        selectedObjectId = result.object.id
        return result
    }
    
    func confirmObject(_ objectId: UUID) async throws {
        _ = try await service.confirmMetadata(objectId: objectId)
        await refreshData()
    }
    
    func publishObject(_ objectId: UUID) async throws {
        _ = try await service.publishObject(objectId: objectId)
        await refreshData()
    }
}
