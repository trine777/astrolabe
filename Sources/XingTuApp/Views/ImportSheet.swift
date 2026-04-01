// 星图 - 导入视图

import SwiftUI
import UniformTypeIdentifiers
import XingTu

struct ImportSheet: View {
    @EnvironmentObject var appState: AppState
    @Environment(\.dismiss) private var dismiss
    
    @State private var isDragging = false
    @State private var importResult: ImportResult?
    @State private var isImporting = false
    @State private var error: String?
    
    var body: some View {
        VStack(spacing: 0) {
            // 头部
            HStack {
                Text("导入数据")
                    .font(.title2)
                    .fontWeight(.bold)
                
                Spacer()
                
                Button(action: { dismiss() }) {
                    Image(systemName: "xmark.circle.fill")
                        .font(.title2)
                        .foregroundColor(.secondary)
                }
                .buttonStyle(.plain)
            }
            .padding()
            
            Divider()
            
            if let result = importResult {
                // 导入预览
                ImportPreviewView(result: result, onConfirm: confirmAndClose, onCancel: resetImport)
            } else {
                // 拖放区域
                DropZone(isDragging: $isDragging, isImporting: $isImporting, error: $error) { url in
                    await performImport(url: url)
                }
            }
        }
        .frame(width: 700, height: 500)
        .background(Color.xingtuBackground)
    }
    
    private func performImport(url: URL) async {
        isImporting = true
        error = nil
        
        do {
            importResult = try await appState.importCSV(url: url)
        } catch {
            self.error = error.localizedDescription
        }
        
        isImporting = false
    }
    
    private func confirmAndClose() {
        if let objectId = importResult?.object.id {
            Task {
                try? await appState.confirmObject(objectId)
            }
        }
        dismiss()
    }
    
    private func resetImport() {
        importResult = nil
    }
}

// MARK: - 拖放区域

struct DropZone: View {
    @Binding var isDragging: Bool
    @Binding var isImporting: Bool
    @Binding var error: String?
    let onDrop: (URL) async -> Void
    
    @State private var showFilePicker = false
    
    var body: some View {
        VStack(spacing: 24) {
            Spacer()
            
            ZStack {
                RoundedRectangle(cornerRadius: 16)
                    .strokeBorder(
                        isDragging ? Color.xingtuAccent : Color.secondary.opacity(0.3),
                        style: StrokeStyle(lineWidth: 2, dash: [8])
                    )
                    .background(
                        RoundedRectangle(cornerRadius: 16)
                            .fill(isDragging ? Color.xingtuAccent.opacity(0.1) : Color.clear)
                    )
                
                VStack(spacing: 16) {
                    if isImporting {
                        ProgressView()
                            .scaleEffect(1.5)
                        Text("正在解析...")
                            .foregroundColor(.secondary)
                    } else {
                        Image(systemName: "doc.badge.arrow.up")
                            .font(.system(size: 48))
                            .foregroundColor(isDragging ? .xingtuAccent : .secondary)
                        
                        Text("拖放 CSV 文件到这里")
                            .font(.title3)
                            .fontWeight(.medium)
                        
                        Text("或")
                            .foregroundColor(.secondary)
                        
                        Button("选择文件...") {
                            showFilePicker = true
                        }
                        .buttonStyle(.bordered)
                    }
                }
            }
            .frame(height: 250)
            .padding(.horizontal, 40)
            .onDrop(of: [.fileURL], isTargeted: $isDragging) { providers in
                handleDrop(providers: providers)
                return true
            }
            
            // 错误提示
            if let error = error {
                HStack {
                    Image(systemName: "exclamationmark.triangle")
                        .foregroundColor(.red)
                    Text(error)
                        .foregroundColor(.red)
                }
                .padding()
                .background(Color.red.opacity(0.1))
                .cornerRadius(8)
            }
            
            // 支持的格式
            HStack(spacing: 16) {
                ForEach(["CSV", "TSV"], id: \.self) { format in
                    HStack(spacing: 4) {
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundColor(.green)
                        Text(format)
                    }
                    .font(.caption)
                    .foregroundColor(.secondary)
                }
            }
            
            Spacer()
        }
        .fileImporter(
            isPresented: $showFilePicker,
            allowedContentTypes: [.commaSeparatedText, UTType(filenameExtension: "tsv") ?? .plainText],
            allowsMultipleSelection: false
        ) { result in
            switch result {
            case .success(let urls):
                if let url = urls.first {
                    Task {
                        await onDrop(url)
                    }
                }
            case .failure(let error):
                self.error = error.localizedDescription
            }
        }
    }
    
    private func handleDrop(providers: [NSItemProvider]) {
        guard let provider = providers.first else { return }
        
        provider.loadItem(forTypeIdentifier: UTType.fileURL.identifier, options: nil) { item, error in
            if let data = item as? Data,
               let url = URL(dataRepresentation: data, relativeTo: nil) {
                Task { @MainActor in
                    await onDrop(url)
                }
            }
        }
    }
}

// MARK: - 导入预览

struct ImportPreviewView: View {
    let result: ImportResult
    let onConfirm: () -> Void
    let onCancel: () -> Void
    
    var body: some View {
        VStack(spacing: 0) {
            // 成功提示
            HStack {
                Image(systemName: "checkmark.circle.fill")
                    .foregroundColor(.green)
                    .font(.title2)
                
                VStack(alignment: .leading) {
                    Text("解析成功")
                        .font(.headline)
                    Text("\(result.object.originalName) - \(result.parseResult.rowCount) 行, \(result.properties.count) 列")
                        .foregroundColor(.secondary)
                }
                
                Spacer()
            }
            .padding()
            .background(Color.green.opacity(0.1))
            
            // 列预览
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    Text("字段预览")
                        .font(.headline)
                        .padding(.horizontal)
                    
                    ForEach(result.properties) { prop in
                        PropertyPreviewRow(property: prop)
                    }
                }
                .padding(.vertical)
            }
            
            Divider()
            
            // 操作按钮
            HStack {
                Button("取消", action: onCancel)
                    .buttonStyle(.bordered)
                
                Spacer()
                
                Button(action: onConfirm) {
                    Label("确认并导入", systemImage: "checkmark.circle")
                }
                .buttonStyle(.borderedProminent)
            }
            .padding()
        }
    }
}

// MARK: - 属性预览行

struct PropertyPreviewRow: View {
    let property: MetaProperty
    
    var body: some View {
        HStack(spacing: 16) {
            // 图标和名称
            HStack(spacing: 8) {
                Image(systemName: property.dataType.icon)
                    .foregroundColor(.xingtuAccent)
                    .frame(width: 24)
                
                Text(property.originalName)
                    .fontWeight(.medium)
            }
            .frame(width: 150, alignment: .leading)
            
            // 数据类型
            Text(property.dataType.displayName)
                .font(.caption)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(Color.secondary.opacity(0.2))
                .cornerRadius(4)
            
            // 统计
            HStack(spacing: 12) {
                Label("\(property.uniqueCount) 唯一", systemImage: "number")
                Label("\(property.nullCount) 空值", systemImage: "minus.circle")
            }
            .font(.caption)
            .foregroundColor(.secondary)
            
            Spacer()
            
            // 样本值
            Text(property.sampleValues.prefix(3).joined(separator: ", "))
                .font(.caption)
                .foregroundColor(.secondary)
                .lineLimit(1)
                .frame(maxWidth: 200)
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
        .background(Color.secondary.opacity(0.05))
        .cornerRadius(8)
        .padding(.horizontal)
    }
}
