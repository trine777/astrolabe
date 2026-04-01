// 星图 - 数据源列表视图

import SwiftUI
import XingTu

struct DataSourceListView: View {
    @EnvironmentObject var appState: AppState
    let filter: MetaObject.Status?
    
    @State private var searchText = ""
    
    private var filteredObjects: [MetaObject] {
        var result = appState.objects
        
        if let status = filter {
            result = result.filter { $0.status == status }
        }
        
        if !searchText.isEmpty {
            result = result.filter {
                $0.name.localizedCaseInsensitiveContains(searchText) ||
                $0.originalName.localizedCaseInsensitiveContains(searchText) ||
                ($0.description?.localizedCaseInsensitiveContains(searchText) ?? false)
            }
        }
        
        return result.sorted { $0.updatedAt > $1.updatedAt }
    }
    
    var body: some View {
        NavigationSplitView {
            List(filteredObjects, selection: $appState.selectedObjectId) { object in
                ObjectRowView(object: object)
                    .tag(object.id)
            }
            .listStyle(.inset)
            .searchable(text: $searchText, prompt: "搜索数据源...")
            .navigationTitle(filter?.displayName ?? "所有数据源")
            .overlay {
                if filteredObjects.isEmpty {
                    EmptyStateView()
                }
            }
        } detail: {
            if let objectId = appState.selectedObjectId,
               let object = appState.objects.first(where: { $0.id == objectId }) {
                ObjectDetailView(object: object)
            } else {
                Text("选择一个数据源查看详情")
                    .foregroundColor(.secondary)
            }
        }
    }
}

// MARK: - 对象行视图

struct ObjectRowView: View {
    let object: MetaObject
    
    var body: some View {
        HStack(spacing: 12) {
            // 类型图标
            Image(systemName: object.objectType.icon)
                .font(.title2)
                .foregroundColor(.xingtuAccent)
                .frame(width: 32)
            
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(object.name)
                        .font(.headline)
                    
                    StatusBadge(status: object.status)
                }
                
                HStack(spacing: 8) {
                    if let rowCount = object.rowCount {
                        Label("\(rowCount) 行", systemImage: "tablecells")
                    }
                    
                    Text(object.updatedAt.formatted(date: .abbreviated, time: .shortened))
                }
                .font(.caption)
                .foregroundColor(.secondary)
            }
            
            Spacer()
        }
        .padding(.vertical, 4)
    }
}

// MARK: - 状态徽章

struct StatusBadge: View {
    let status: MetaObject.Status
    
    var body: some View {
        Text(status.displayName)
            .font(.caption2)
            .fontWeight(.medium)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(backgroundColor)
            .foregroundColor(.white)
            .clipShape(Capsule())
    }
    
    private var backgroundColor: Color {
        switch status {
        case .draft: return .orange
        case .confirmed: return .blue
        case .published: return .green
        case .archived: return .gray
        }
    }
}

// MARK: - 空状态视图

struct EmptyStateView: View {
    @EnvironmentObject var appState: AppState
    
    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "doc.badge.plus")
                .font(.system(size: 48))
                .foregroundColor(.secondary)
            
            Text("暂无数据源")
                .font(.title2)
                .fontWeight(.medium)
            
            Text("拖入 CSV 文件或点击导入按钮开始")
                .foregroundColor(.secondary)
            
            Button("导入数据") {
                appState.showImportSheet = true
            }
            .buttonStyle(.borderedProminent)
        }
        .padding(40)
    }
}
