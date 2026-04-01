// 星图 (XingTu) - 元数据编辑器视图
// 归属: 语界枢 (Yujieshu)

import SwiftUI

/// 语界枢：元数据编辑器
public struct MetaEditorView: View {
    
    // MARK: - 状态
    
    @Binding var object: MetaObject
    @Binding var properties: [MetaProperty]
    @State private var selectedPropertyId: UUID?
    @State private var isEditing = false
    
    // MARK: - 回调
    
    public var onConfirm: () -> Void
    public var onCancel: () -> Void
    
    // MARK: - 初始化
    
    public init(
        object: Binding<MetaObject>,
        properties: Binding<[MetaProperty]>,
        onConfirm: @escaping () -> Void,
        onCancel: @escaping () -> Void
    ) {
        self._object = object
        self._properties = properties
        self.onConfirm = onConfirm
        self.onCancel = onCancel
    }
    
    // MARK: - 视图
    
    public var body: some View {
        VStack(spacing: 0) {
            // 顶部栏
            headerBar
            
            Divider()
                .background(Color.white.opacity(0.1))
            
            // 对象信息
            objectInfoSection
            
            Divider()
                .background(Color.white.opacity(0.1))
            
            // 属性列表
            propertyListSection
            
            Divider()
                .background(Color.white.opacity(0.1))
            
            // 底部操作栏
            actionBar
        }
        .background(Color.white.opacity(0.02))
        .cornerRadius(12)
    }
    
    // MARK: - 顶部栏
    
    private var headerBar: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text("元数据编辑")
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundColor(Color.white.opacity(0.9))
                
                Text(object.originalName)
                    .font(.system(size: 12, weight: .light))
                    .foregroundColor(Color.white.opacity(0.5))
            }
            
            Spacer()
            
            // 状态标签
            statusBadge
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
    }
    
    private var statusBadge: some View {
        HStack(spacing: 4) {
            Circle()
                .fill(statusColor)
                .frame(width: 6, height: 6)
            
            Text(object.status.displayName)
                .font(.system(size: 11, weight: .medium))
                .foregroundColor(Color.white.opacity(0.7))
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 4)
        .background(statusColor.opacity(0.15))
        .cornerRadius(12)
    }
    
    private var statusColor: Color {
        switch object.status {
        case .draft: return .orange
        case .confirmed: return .blue
        case .published: return .green
        case .archived: return .gray
        }
    }
    
    // MARK: - 对象信息
    
    private var objectInfoSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            // 名称
            VStack(alignment: .leading, spacing: 4) {
                Text("业务名称")
                    .font(.system(size: 11, weight: .medium))
                    .foregroundColor(Color.white.opacity(0.5))
                
                TextField("输入名称", text: $object.name)
                    .textFieldStyle(.plain)
                    .font(.system(size: 14))
                    .foregroundColor(Color.white.opacity(0.9))
                    .padding(10)
                    .background(Color.white.opacity(0.05))
                    .cornerRadius(8)
            }
            
            // 描述
            VStack(alignment: .leading, spacing: 4) {
                Text("业务描述")
                    .font(.system(size: 11, weight: .medium))
                    .foregroundColor(Color.white.opacity(0.5))
                
                TextField("描述这个数据集", text: Binding(
                    get: { object.description ?? "" },
                    set: { object.description = $0.isEmpty ? nil : $0 }
                ))
                .textFieldStyle(.plain)
                .font(.system(size: 14))
                .foregroundColor(Color.white.opacity(0.9))
                .padding(10)
                .background(Color.white.opacity(0.05))
                .cornerRadius(8)
            }
            
            // 统计信息
            HStack(spacing: 16) {
                StatItem(label: "行数", value: "\(object.rowCount ?? 0)")
                StatItem(label: "列数", value: "\(properties.count)")
                StatItem(label: "类型", value: object.objectType.displayName)
            }
        }
        .padding(16)
    }
    
    // MARK: - 属性列表
    
    private var propertyListSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            // 表头
            HStack {
                Text("属性")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundColor(Color.white.opacity(0.5))
                
                Spacer()
                
                Text("\(properties.count) 列")
                    .font(.system(size: 11))
                    .foregroundColor(Color.white.opacity(0.4))
            }
            .padding(.horizontal, 16)
            .padding(.top, 12)
            
            // 列表
            ScrollView {
                LazyVStack(spacing: 2) {
                    ForEach($properties) { $prop in
                        PropertyRow(
                            property: $prop,
                            isSelected: selectedPropertyId == prop.id,
                            onTap: { selectedPropertyId = prop.id }
                        )
                    }
                }
                .padding(.horizontal, 8)
            }
            .frame(maxHeight: 300)
        }
    }
    
    // MARK: - 底部操作栏
    
    private var actionBar: some View {
        HStack {
            Button(action: onCancel) {
                Text("取消")
                    .font(.system(size: 13, weight: .medium))
                    .foregroundColor(Color.white.opacity(0.6))
                    .padding(.horizontal, 20)
                    .padding(.vertical, 8)
                    .background(Color.white.opacity(0.05))
                    .cornerRadius(8)
            }
            .buttonStyle(.plain)
            
            Spacer()
            
            Button(action: onConfirm) {
                HStack(spacing: 6) {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 14))
                    Text("确认元数据")
                        .font(.system(size: 13, weight: .medium))
                }
                .foregroundColor(.white)
                .padding(.horizontal, 20)
                .padding(.vertical, 8)
                .background(
                    LinearGradient(
                        colors: [
                            Color(red: 0.4, green: 0.6, blue: 0.9),
                            Color(red: 0.6, green: 0.5, blue: 0.8)
                        ],
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                )
                .cornerRadius(8)
            }
            .buttonStyle(.plain)
        }
        .padding(16)
    }
}

// MARK: - 统计项

private struct StatItem: View {
    let label: String
    let value: String
    
    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label)
                .font(.system(size: 10, weight: .medium))
                .foregroundColor(Color.white.opacity(0.4))
            Text(value)
                .font(.system(size: 14, weight: .medium))
                .foregroundColor(Color.white.opacity(0.8))
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(Color.white.opacity(0.03))
        .cornerRadius(8)
    }
}

// MARK: - 属性行

private struct PropertyRow: View {
    @Binding var property: MetaProperty
    let isSelected: Bool
    let onTap: () -> Void
    
    var body: some View {
        HStack(spacing: 12) {
            // 数据类型图标
            Image(systemName: property.dataType.icon)
                .font(.system(size: 12))
                .foregroundColor(Color.white.opacity(0.5))
                .frame(width: 24)
            
            // 列名
            VStack(alignment: .leading, spacing: 2) {
                Text(property.displayName)
                    .font(.system(size: 13, weight: .medium))
                    .foregroundColor(Color.white.opacity(0.9))
                
                Text(property.originalName)
                    .font(.system(size: 10))
                    .foregroundColor(Color.white.opacity(0.4))
            }
            
            Spacer()
            
            // 语义类型
            if let semanticType = property.semanticType {
                HStack(spacing: 4) {
                    if property.aiInferred != nil {
                        Image(systemName: "brain")
                            .font(.system(size: 9))
                            .foregroundColor(Color.purple.opacity(0.7))
                    }
                    Text(semanticType.displayName)
                        .font(.system(size: 11))
                        .foregroundColor(Color.white.opacity(0.6))
                }
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(Color.white.opacity(0.05))
                .cornerRadius(6)
            }
            
            // AI 置信度
            if let ai = property.aiInferred {
                Text("\(Int(ai.confidence * 100))%")
                    .font(.system(size: 10, weight: .medium))
                    .foregroundColor(confidenceColor(ai.confidence))
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .background(isSelected ? Color.white.opacity(0.08) : Color.clear)
        .cornerRadius(8)
        .contentShape(Rectangle())
        .onTapGesture(perform: onTap)
    }
    
    private func confidenceColor(_ confidence: Double) -> Color {
        if confidence >= 0.8 {
            return .green.opacity(0.8)
        } else if confidence >= 0.5 {
            return .orange.opacity(0.8)
        } else {
            return .red.opacity(0.8)
        }
    }
}

// MARK: - 预览

#if DEBUG
struct MetaEditorView_Previews: PreviewProvider {
    static var previews: some View {
        MetaEditorView(
            object: .constant(MetaObject(
                name: "销售数据",
                originalName: "sales_2024.csv",
                objectType: .csvFile,
                description: "2024年销售记录",
                rowCount: 1500
            )),
            properties: .constant([
                MetaProperty(
                    objectId: UUID(),
                    originalName: "order_id",
                    dataType: .string,
                    sampleValues: ["ORD001", "ORD002"],
                    displayName: "订单ID",
                    semanticType: .primaryKey,
                    aiInferred: MetaProperty.AIInferredInfo(
                        inferredSemanticType: .primaryKey,
                        confidence: 0.95
                    )
                ),
                MetaProperty(
                    objectId: UUID(),
                    originalName: "amount",
                    dataType: .decimal,
                    sampleValues: ["199.99", "299.00"],
                    displayName: "金额",
                    semanticType: .amount,
                    unit: "元",
                    aiInferred: MetaProperty.AIInferredInfo(
                        inferredSemanticType: .amount,
                        confidence: 0.88
                    )
                )
            ]),
            onConfirm: {},
            onCancel: {}
        )
        .frame(width: 500, height: 600)
        .background(Color(red: 0.06, green: 0.06, blue: 0.10))
        .preferredColorScheme(.dark)
    }
}
#endif
