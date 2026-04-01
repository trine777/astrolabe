// 星图 - 主视图

import SwiftUI
import XingTu

struct MainView: View {
    @EnvironmentObject var appState: AppState
    
    var body: some View {
        NavigationSplitView {
            SidebarView()
        } detail: {
            DetailView()
        }
        .background(Color.xingtuBackground)
        .sheet(isPresented: $appState.showImportSheet) {
            ImportSheet()
        }
        .alert("错误", isPresented: .constant(appState.errorMessage != nil)) {
            Button("确定") {
                appState.errorMessage = nil
            }
        } message: {
            Text(appState.errorMessage ?? "")
        }
    }
}

// MARK: - 侧边栏

struct SidebarView: View {
    @EnvironmentObject var appState: AppState
    
    var body: some View {
        List(selection: $appState.sidebarSelection) {
            Section("数据源") {
                ForEach([AppState.SidebarItem.allObjects, .drafts, .confirmed, .published], id: \.self) { item in
                    Label {
                        HStack {
                            Text(item.rawValue)
                            Spacer()
                            Text("\(count(for: item))")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    } icon: {
                        Image(systemName: item.icon)
                            .foregroundColor(color(for: item))
                    }
                    .tag(item)
                }
            }
            
            Section("视图") {
                ForEach([AppState.SidebarItem.worldModel, .events], id: \.self) { item in
                    Label(item.rawValue, systemImage: item.icon)
                        .tag(item)
                }
            }
        }
        .listStyle(.sidebar)
        .navigationTitle("星图")
        .toolbar {
            ToolbarItem {
                Button(action: { appState.showImportSheet = true }) {
                    Image(systemName: "plus")
                }
                .help("导入数据")
            }
            
            ToolbarItem {
                Button(action: { Task { await appState.refreshData() } }) {
                    Image(systemName: "arrow.clockwise")
                }
                .help("刷新")
            }
        }
    }
    
    private func count(for item: AppState.SidebarItem) -> Int {
        switch item {
        case .allObjects: return appState.objects.count
        case .drafts: return appState.objects.filter { $0.status == .draft }.count
        case .confirmed: return appState.objects.filter { $0.status == .confirmed }.count
        case .published: return appState.objects.filter { $0.status == .published }.count
        default: return 0
        }
    }
    
    private func color(for item: AppState.SidebarItem) -> Color {
        switch item {
        case .drafts: return .orange
        case .confirmed: return .blue
        case .published: return .green
        default: return .secondary
        }
    }
}

// MARK: - 详情视图

struct DetailView: View {
    @EnvironmentObject var appState: AppState
    
    var body: some View {
        Group {
            switch appState.sidebarSelection {
            case .allObjects, .drafts, .confirmed, .published:
                DataSourceListView(filter: statusFilter)
            case .worldModel:
                WorldModelView()
            case .events:
                EventHistoryView()
            }
        }
    }
    
    private var statusFilter: MetaObject.Status? {
        switch appState.sidebarSelection {
        case .drafts: return .draft
        case .confirmed: return .confirmed
        case .published: return .published
        default: return nil
        }
    }
}
