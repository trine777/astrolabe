// 星图 - 对象详情视图

import SwiftUI
import XingTu

struct ObjectDetailView: View {
    @EnvironmentObject var appState: AppState
    let object: MetaObject
    
    @State private var properties: [MetaProperty] = []
    @State private var events: [MetaEvent] = []
    @State private var isLoading = true
    @State private var selectedTab = 0
    @State private var showAIAssistant = false
    
    var body: some View {
        HStack(spacing: 0) {
            // 主内容区
            VStack(spacing: 0) {
                // 头部信息
                ObjectHeader(object: object, showAIAssistant: $showAIAssistant)
                
                Divider()
                
                // 标签页
                Picker("", selection: $selectedTab) {
                    Text("字段 (\(properties.count))").tag(0)
                    Text("变更记录").tag(1)
                }
                .pickerStyle(.segmented)
                .padding()
                
                // 内容
                if isLoading {
                    ProgressView()
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
                    TabView(selection: $selectedTab) {
                        EditablePropertiesListView(objectId: object.id, properties: $properties)
                            .tag(0)
                        
                        ObjectEventsView(events: events)
                            .tag(1)
                    }
                    .tabViewStyle(.automatic)
                }
            }
            
            // AI 助手侧边栏
            if showAIAssistant {
                Divider()
                
                AIAssistantView(object: object, properties: $properties)
                    .transition(.move(edge: .trailing))
            }
        }
        .background(Color.xingtuBackground)
        .task(id: object.id) {
            await loadData()
        }
        .animation(.xingtuSpring, value: showAIAssistant)
    }
    
    private func loadData() async {
        isLoading = true
        defer { isLoading = false }
        
        do {
            properties = try await appState.service.getProperties(objectId: object.id)
            events = try await appState.service.getObjectHistory(objectId: object.id)
        } catch {
            appState.errorMessage = error.localizedDescription
        }
    }
}

// MARK: - 对象头部

struct ObjectHeader: View {
    @EnvironmentObject var appState: AppState
    let object: MetaObject
    @Binding var showAIAssistant: Bool
    
    @State private var isConfirming = false
    @State private var isPublishing = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(alignment: .top) {
                // 图标和名称
                HStack(spacing: 12) {
                    Image(systemName: object.objectType.icon)
                        .font(.largeTitle)
                        .foregroundColor(.xingtuAccent)
                    
                    VStack(alignment: .leading, spacing: 4) {
                        HStack {
                            Text(object.name)
                                .font(.title2)
                                .fontWeight(.bold)
                            
                            StatusBadge(status: object.status)
                        }
                        
                        Text(object.originalName)
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                    }
                }
                
                Spacer()
                
                // 操作按钮
                HStack(spacing: 12) {
                    // AI 助手按钮
                    Button(action: { showAIAssistant.toggle() }) {
                        Label("AI 助手", systemImage: "sparkles")
                    }
                    .buttonStyle(.bordered)
                    .tint(showAIAssistant ? .xingtuAccent : nil)
                    
                    if object.status == .draft {
                        Button(action: confirmObject) {
                            Label("确认", systemImage: "checkmark.circle")
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(isConfirming)
                    }
                    
                    if object.status == .confirmed {
                        Button(action: publishObject) {
                            Label("发布", systemImage: "arrow.up.circle")
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(.green)
                        .disabled(isPublishing)
                    }
                }
            }
            
            // 元信息
            HStack(spacing: 24) {
                if let rowCount = object.rowCount {
                    InfoItem(icon: "tablecells", label: "行数", value: "\(rowCount)")
                }
                
                InfoItem(icon: "calendar", label: "创建时间", value: object.createdAt.formatted())
                
                if let confirmedAt = object.confirmedAt {
                    InfoItem(icon: "checkmark.circle", label: "确认时间", value: confirmedAt.formatted())
                }
            }
            
            // 描述
            if let description = object.description, !description.isEmpty {
                Text(description)
                    .font(.body)
                    .foregroundColor(.secondary)
            }
            
            // 标签
            if !object.tags.isEmpty {
                HStack {
                    ForEach(object.tags, id: \.self) { tag in
                        Text(tag)
                            .font(.caption)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(Color.xingtuAccent.opacity(0.2))
                            .foregroundColor(.xingtuAccent)
                            .clipShape(Capsule())
                    }
                }
            }
        }
        .padding()
    }
    
    private func confirmObject() {
        isConfirming = true
        Task {
            do {
                try await appState.confirmObject(object.id)
            } catch {
                appState.errorMessage = error.localizedDescription
            }
            isConfirming = false
        }
    }
    
    private func publishObject() {
        isPublishing = true
        Task {
            do {
                try await appState.publishObject(object.id)
            } catch {
                appState.errorMessage = error.localizedDescription
            }
            isPublishing = false
        }
    }
}

// MARK: - 信息项

struct InfoItem: View {
    let icon: String
    let label: String
    let value: String
    
    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: icon)
                .foregroundColor(.secondary)
            Text(label + ":")
                .foregroundColor(.secondary)
            Text(value)
        }
        .font(.caption)
    }
}

// MARK: - 可编辑属性列表视图

struct EditablePropertiesListView: View {
    @EnvironmentObject var appState: AppState
    let objectId: UUID
    @Binding var properties: [MetaProperty]
    
    @State private var selectedPropertyId: UUID?
    @State private var editingPropertyId: UUID?
    
    var body: some View {
        VStack(spacing: 0) {
            // 工具栏
            HStack {
                Text("双击业务名称可快速编辑，点击铅笔图标打开详细编辑器")
                    .font(.caption)
                    .foregroundColor(.secondary)
                
                Spacer()
                
                Button(action: {}) {
                    Label("批量编辑", systemImage: "square.and.pencil")
                }
                .buttonStyle(.bordered)
                .controlSize(.small)
            }
            .padding(.horizontal)
            .padding(.vertical, 8)
            .background(Color.xingtuSecondaryBackground.opacity(0.5))
            
            // 表格头部
            HStack(spacing: 0) {
                Text("字段名")
                    .frame(width: 140, alignment: .leading)
                Text("业务名称")
                    .frame(width: 160, alignment: .leading)
                Text("数据类型")
                    .frame(width: 80, alignment: .leading)
                Text("语义类型")
                    .frame(width: 100, alignment: .leading)
                Text("空值")
                    .frame(width: 60, alignment: .trailing)
                Text("唯一值")
                    .frame(width: 60, alignment: .trailing)
                Text("样本值")
                    .frame(minWidth: 100, alignment: .leading)
                Spacer()
                Text("操作")
                    .frame(width: 50)
            }
            .font(.caption)
            .fontWeight(.medium)
            .foregroundColor(.secondary)
            .padding(.horizontal)
            .padding(.vertical, 8)
            .background(Color.secondary.opacity(0.1))
            
            // 属性列表
            ScrollView {
                LazyVStack(spacing: 1) {
                    ForEach($properties) { $prop in
                        EditablePropertyRow(
                            objectId: objectId,
                            property: $prop,
                            isSelected: selectedPropertyId == prop.id,
                            isEditing: editingPropertyId == prop.id
                        ) {
                            selectedPropertyId = prop.id
                        } onStartEdit: {
                            editingPropertyId = prop.id
                        } onEndEdit: {
                            editingPropertyId = nil
                        }
                    }
                }
            }
        }
    }
}

// MARK: - 可编辑属性行

struct EditablePropertyRow: View {
    @EnvironmentObject var appState: AppState
    let objectId: UUID
    @Binding var property: MetaProperty
    let isSelected: Bool
    let isEditing: Bool
    let onSelect: () -> Void
    let onStartEdit: () -> Void
    let onEndEdit: () -> Void
    
    @State private var editedDisplayName: String = ""
    @State private var showingDetailEditor = false
    
    var body: some View {
        HStack(spacing: 0) {
            // 字段名
            HStack(spacing: 6) {
                Image(systemName: property.dataType.icon)
                    .foregroundColor(.xingtuAccent)
                    .frame(width: 18)
                Text(property.originalName)
                    .fontWeight(.medium)
                    .lineLimit(1)
            }
            .frame(width: 140, alignment: .leading)
            
            // 业务名称（可编辑）
            Group {
                if isEditing {
                    HStack(spacing: 4) {
                        TextField("", text: $editedDisplayName)
                            .textFieldStyle(.roundedBorder)
                            .frame(width: 120)
                            .onSubmit { saveDisplayName() }
                        
                        Button(action: saveDisplayName) {
                            Image(systemName: "checkmark")
                                .foregroundColor(.green)
                        }
                        .buttonStyle(.plain)
                        
                        Button(action: cancelEdit) {
                            Image(systemName: "xmark")
                                .foregroundColor(.red)
                        }
                        .buttonStyle(.plain)
                    }
                } else {
                    Text(property.displayName)
                        .lineLimit(1)
                        .onTapGesture(count: 2) {
                            editedDisplayName = property.displayName
                            onStartEdit()
                        }
                }
            }
            .frame(width: 160, alignment: .leading)
            
            // 数据类型
            Text(property.dataType.displayName)
                .font(.caption)
                .foregroundColor(.secondary)
                .frame(width: 80, alignment: .leading)
            
            // 语义类型
            Group {
                if let semanticType = property.semanticType {
                    Text(semanticType.displayName)
                        .font(.caption)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(Color.xingtuAccent.opacity(0.2))
                        .cornerRadius(4)
                } else {
                    Text("-")
                        .foregroundColor(.secondary)
                }
            }
            .frame(width: 100, alignment: .leading)
            
            // 空值
            Text("\(property.nullCount)")
                .foregroundColor(property.nullCount > 0 ? .orange : .secondary)
                .frame(width: 60, alignment: .trailing)
            
            // 唯一值
            Text("\(property.uniqueCount)")
                .frame(width: 60, alignment: .trailing)
            
            // 样本值
            Text(property.sampleValues.prefix(3).joined(separator: ", "))
                .font(.caption)
                .foregroundColor(.secondary)
                .lineLimit(1)
                .frame(minWidth: 100, alignment: .leading)
            
            Spacer()
            
            // 操作按钮
            Button(action: { showingDetailEditor = true }) {
                Image(systemName: "pencil.circle")
                    .foregroundColor(.secondary)
            }
            .buttonStyle(.plain)
            .frame(width: 50)
        }
        .font(.system(size: 13))
        .padding(.horizontal)
        .padding(.vertical, 10)
        .background(isSelected ? Color.xingtuAccent.opacity(0.1) : Color.clear)
        .contentShape(Rectangle())
        .onTapGesture { onSelect() }
        .popover(isPresented: $showingDetailEditor) {
            PropertyEditorView(objectId: objectId, property: $property)
        }
    }
    
    private func saveDisplayName() {
        guard !editedDisplayName.isEmpty else {
            cancelEdit()
            return
        }
        
        let oldName = property.displayName
        var updated = property
        updated.displayName = editedDisplayName
        
        Task {
            do {
                _ = try await appState.service.metaStore.updateProperty(updated)
                
                await appState.service.eventStream.emitPropertyUpdated(
                    objectId: objectId,
                    propertyId: property.id,
                    by: .user,
                    before: oldName,
                    after: editedDisplayName
                )
                
                property = updated
            } catch {
                appState.errorMessage = error.localizedDescription
            }
        }
        
        onEndEdit()
    }
    
    private func cancelEdit() {
        onEndEdit()
    }
}

// MARK: - 原属性列表视图（只读）

struct PropertiesListView: View {
    let properties: [MetaProperty]
    
    var body: some View {
        Table(properties) {
            TableColumn("字段名") { prop in
                HStack {
                    Image(systemName: prop.dataType.icon)
                        .foregroundColor(.xingtuAccent)
                    Text(prop.originalName)
                        .fontWeight(.medium)
                }
            }
            .width(min: 120, ideal: 150)
            
            TableColumn("业务名称") { prop in
                Text(prop.displayName)
            }
            .width(min: 100, ideal: 120)
            
            TableColumn("数据类型") { prop in
                Text(prop.dataType.displayName)
                    .foregroundColor(.secondary)
            }
            .width(80)
            
            TableColumn("语义类型") { prop in
                if let semanticType = prop.semanticType {
                    Text(semanticType.displayName)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(Color.xingtuAccent.opacity(0.15))
                        .clipShape(Capsule())
                } else {
                    Text("-")
                        .foregroundColor(.secondary)
                }
            }
            .width(100)
            
            TableColumn("空值") { prop in
                Text("\(prop.nullCount)")
                    .foregroundColor(prop.nullCount > 0 ? .orange : .secondary)
            }
            .width(60)
            
            TableColumn("唯一值") { prop in
                Text("\(prop.uniqueCount)")
            }
            .width(60)
            
            TableColumn("样本值") { prop in
                Text(prop.sampleValues.prefix(3).joined(separator: ", "))
                    .lineLimit(1)
                    .foregroundColor(.secondary)
            }
        }
        .tableStyle(.inset)
    }
}

// MARK: - 对象事件视图

struct ObjectEventsView: View {
    let events: [MetaEvent]
    
    var body: some View {
        List(events) { event in
            HStack(spacing: 12) {
                Image(systemName: event.eventType.icon)
                    .font(.title3)
                    .foregroundColor(eventColor(event.eventType))
                    .frame(width: 28)
                
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text(event.eventType.displayName)
                            .fontWeight(.medium)
                        
                        Spacer()
                        
                        Text(event.timestamp.formatted(date: .abbreviated, time: .shortened))
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    
                    if let description = event.description {
                        Text(description)
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                    }
                    
                    HStack {
                        Image(systemName: event.actorType.icon)
                        Text(event.actorType.displayName)
                        if let actorId = event.actorId {
                            Text("(\(actorId))")
                        }
                    }
                    .font(.caption)
                    .foregroundColor(.secondary)
                }
            }
            .padding(.vertical, 4)
        }
    }
    
    private func eventColor(_ type: MetaEvent.EventType) -> Color {
        switch type.category {
        case .object: return .blue
        case .property: return .purple
        case .relation: return .orange
        case .bulk: return .green
        }
    }
}
