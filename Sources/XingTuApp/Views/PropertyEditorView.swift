// 星图 - 属性编辑器视图
// 支持人工编辑和 AI 对话式修改

import SwiftUI
import XingTu

struct PropertyEditorView: View {
    @EnvironmentObject var appState: AppState
    let objectId: UUID
    @Binding var property: MetaProperty
    
    @State private var editedDisplayName: String = ""
    @State private var editedDescription: String = ""
    @State private var editedSemanticType: MetaProperty.SemanticType?
    @State private var editedUnit: String = ""
    @State private var isEditing = false
    @State private var isSaving = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // 头部
            HStack {
                Image(systemName: property.dataType.icon)
                    .font(.title2)
                    .foregroundColor(.xingtuAccent)
                
                VStack(alignment: .leading) {
                    Text(property.originalName)
                        .font(.headline)
                    Text(property.dataType.displayName)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                if isEditing {
                    Button("取消") {
                        cancelEditing()
                    }
                    .buttonStyle(.bordered)
                    
                    Button("保存") {
                        saveChanges()
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(isSaving)
                } else {
                    Button("编辑") {
                        startEditing()
                    }
                    .buttonStyle(.bordered)
                }
            }
            
            Divider()
            
            // 编辑表单
            Form {
                Section("业务信息") {
                    LabeledContent("业务名称") {
                        if isEditing {
                            TextField("输入业务名称", text: $editedDisplayName)
                                .textFieldStyle(.roundedBorder)
                        } else {
                            Text(property.displayName)
                        }
                    }
                    
                    LabeledContent("业务描述") {
                        if isEditing {
                            TextField("输入业务描述", text: $editedDescription)
                                .textFieldStyle(.roundedBorder)
                        } else {
                            Text(property.description ?? "-")
                                .foregroundColor(property.description == nil ? .secondary : .primary)
                        }
                    }
                    
                    LabeledContent("语义类型") {
                        if isEditing {
                            Picker("", selection: $editedSemanticType) {
                                Text("未指定").tag(nil as MetaProperty.SemanticType?)
                                ForEach(MetaProperty.SemanticType.allCases, id: \.self) { type in
                                    Text(type.displayName).tag(type as MetaProperty.SemanticType?)
                                }
                            }
                        } else {
                            if let semanticType = property.semanticType {
                                Text(semanticType.displayName)
                                    .padding(.horizontal, 8)
                                    .padding(.vertical, 4)
                                    .background(Color.xingtuAccent.opacity(0.2))
                                    .cornerRadius(4)
                            } else {
                                Text("-")
                                    .foregroundColor(.secondary)
                            }
                        }
                    }
                    
                    LabeledContent("单位") {
                        if isEditing {
                            TextField("如：元、%、人", text: $editedUnit)
                                .textFieldStyle(.roundedBorder)
                        } else {
                            Text(property.unit ?? "-")
                                .foregroundColor(property.unit == nil ? .secondary : .primary)
                        }
                    }
                }
                
                Section("统计信息") {
                    LabeledContent("空值数量") {
                        Text("\(property.nullCount)")
                            .foregroundColor(property.nullCount > 0 ? .orange : .secondary)
                    }
                    
                    LabeledContent("唯一值数量") {
                        Text("\(property.uniqueCount)")
                    }
                    
                    LabeledContent("样本值") {
                        Text(property.sampleValues.prefix(5).joined(separator: ", "))
                            .foregroundColor(.secondary)
                            .lineLimit(2)
                    }
                }
                
                // AI 推断信息
                if let aiInfo = property.aiInferred {
                    Section("AI 推断") {
                        LabeledContent("推断类型") {
                            if let inferredType = aiInfo.inferredSemanticType {
                                Text(inferredType.displayName)
                            } else {
                                Text("-")
                            }
                        }
                        
                        LabeledContent("置信度") {
                            Text(String(format: "%.0f%%", aiInfo.confidence * 100))
                        }
                        
                        if let reasoning = aiInfo.reasoning {
                            LabeledContent("推理说明") {
                                Text(reasoning)
                                    .foregroundColor(.secondary)
                            }
                        }
                    }
                }
            }
            .formStyle(.grouped)
        }
        .padding()
        .frame(width: 400)
    }
    
    private func startEditing() {
        editedDisplayName = property.displayName
        editedDescription = property.description ?? ""
        editedSemanticType = property.semanticType
        editedUnit = property.unit ?? ""
        isEditing = true
    }
    
    private func cancelEditing() {
        isEditing = false
    }
    
    private func saveChanges() {
        isSaving = true
        
        // 更新属性
        var updated = property
        updated.displayName = editedDisplayName
        updated.description = editedDescription.isEmpty ? nil : editedDescription
        updated.semanticType = editedSemanticType
        updated.unit = editedUnit.isEmpty ? nil : editedUnit
        
        Task {
            do {
                _ = try await appState.service.metaStore.updateProperty(updated)
                
                // 发送事件
                await appState.service.eventStream.emitPropertyUpdated(
                    objectId: objectId,
                    propertyId: property.id,
                    by: .user,
                    before: property.displayName,
                    after: updated.displayName
                )
                
                property = updated
                isEditing = false
            } catch {
                appState.errorMessage = error.localizedDescription
            }
            isSaving = false
        }
    }
}

// MARK: - 快速编辑行

struct QuickEditPropertyRow: View {
    @EnvironmentObject var appState: AppState
    let objectId: UUID
    @Binding var property: MetaProperty
    
    @State private var isEditing = false
    @State private var editedDisplayName: String = ""
    @State private var showingEditor = false
    
    var body: some View {
        HStack(spacing: 12) {
            // 数据类型图标
            Image(systemName: property.dataType.icon)
                .foregroundColor(.xingtuAccent)
                .frame(width: 24)
            
            // 原始名称
            Text(property.originalName)
                .fontWeight(.medium)
                .frame(width: 120, alignment: .leading)
            
            // 业务名称（可编辑）
            if isEditing {
                TextField("业务名称", text: $editedDisplayName)
                    .textFieldStyle(.roundedBorder)
                    .frame(width: 150)
                    .onSubmit {
                        saveDisplayName()
                    }
                
                Button(action: saveDisplayName) {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.green)
                }
                .buttonStyle(.plain)
                
                Button(action: cancelEditing) {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(.red)
                }
                .buttonStyle(.plain)
            } else {
                Text(property.displayName)
                    .frame(width: 150, alignment: .leading)
                    .onTapGesture(count: 2) {
                        startEditing()
                    }
            }
            
            // 数据类型
            Text(property.dataType.displayName)
                .font(.caption)
                .foregroundColor(.secondary)
                .frame(width: 60)
            
            // 语义类型
            if let semanticType = property.semanticType {
                Text(semanticType.displayName)
                    .font(.caption)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Color.xingtuAccent.opacity(0.2))
                    .cornerRadius(4)
            } else {
                Text("-")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
            
            // 详细编辑按钮
            Button(action: { showingEditor = true }) {
                Image(systemName: "pencil.circle")
            }
            .buttonStyle(.plain)
            .foregroundColor(.secondary)
        }
        .padding(.vertical, 6)
        .padding(.horizontal, 12)
        .background(Color.secondary.opacity(0.05))
        .cornerRadius(8)
        .popover(isPresented: $showingEditor) {
            PropertyEditorView(objectId: objectId, property: $property)
        }
    }
    
    private func startEditing() {
        editedDisplayName = property.displayName
        isEditing = true
    }
    
    private func cancelEditing() {
        isEditing = false
    }
    
    private func saveDisplayName() {
        guard !editedDisplayName.isEmpty else {
            cancelEditing()
            return
        }
        
        var updated = property
        updated.displayName = editedDisplayName
        
        Task {
            do {
                _ = try await appState.service.metaStore.updateProperty(updated)
                
                await appState.service.eventStream.emitPropertyUpdated(
                    objectId: objectId,
                    propertyId: property.id,
                    by: .user,
                    before: property.displayName,
                    after: editedDisplayName
                )
                
                property = updated
            } catch {
                appState.errorMessage = error.localizedDescription
            }
        }
        
        isEditing = false
    }
}
