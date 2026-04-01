// 星图 (XingTu) - 拖放区域视图
// 归属: 语界枢 (Yujieshu)

import SwiftUI
import UniformTypeIdentifiers

/// 语界枢：文件拖放区域
public struct DropZoneView: View {
    
    // MARK: - 状态
    
    @State private var isDragging = false
    @State private var isProcessing = false
    @State private var errorMessage: String?
    
    // MARK: - 回调
    
    public var onFilesDropped: ([URL]) -> Void
    
    // MARK: - 初始化
    
    public init(onFilesDropped: @escaping ([URL]) -> Void) {
        self.onFilesDropped = onFilesDropped
    }
    
    // MARK: - 视图
    
    public var body: some View {
        ZStack {
            // 背景
            RoundedRectangle(cornerRadius: 16)
                .fill(backgroundColor)
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .strokeBorder(
                            style: StrokeStyle(lineWidth: 2, dash: [8, 4])
                        )
                        .foregroundColor(borderColor)
                )
            
            // 内容
            VStack(spacing: 16) {
                if isProcessing {
                    ProgressView()
                        .scaleEffect(1.5)
                    Text("正在解析...")
                        .font(.system(size: 14, weight: .medium))
                        .foregroundColor(Color.white.opacity(0.7))
                } else {
                    Image(systemName: iconName)
                        .font(.system(size: 48, weight: .light))
                        .foregroundColor(iconColor)
                    
                    VStack(spacing: 4) {
                        Text(titleText)
                            .font(.system(size: 16, weight: .medium))
                            .foregroundColor(Color.white.opacity(0.9))
                        
                        Text(subtitleText)
                            .font(.system(size: 12, weight: .light))
                            .foregroundColor(Color.white.opacity(0.5))
                    }
                    
                    if let error = errorMessage {
                        Text(error)
                            .font(.system(size: 12))
                            .foregroundColor(Color.red.opacity(0.8))
                            .padding(.top, 8)
                    }
                }
            }
            .padding(32)
        }
        .frame(minHeight: 200)
        .onDrop(of: supportedTypes, isTargeted: $isDragging) { providers in
            handleDrop(providers: providers)
            return true
        }
        .animation(.easeInOut(duration: 0.2), value: isDragging)
    }
    
    // MARK: - 样式计算
    
    private var backgroundColor: Color {
        if isDragging {
            return Color(red: 0.4, green: 0.6, blue: 0.9).opacity(0.15)  // 风蓝
        }
        return Color.white.opacity(0.03)
    }
    
    private var borderColor: Color {
        if isDragging {
            return Color(red: 0.4, green: 0.6, blue: 0.9).opacity(0.6)  // 风蓝
        }
        return Color.white.opacity(0.1)
    }
    
    private var iconName: String {
        if isDragging {
            return "arrow.down.doc.fill"
        }
        return "doc.badge.plus"
    }
    
    private var iconColor: Color {
        if isDragging {
            return Color(red: 0.4, green: 0.6, blue: 0.9)  // 风蓝
        }
        return Color.white.opacity(0.4)
    }
    
    private var titleText: String {
        if isDragging {
            return "释放以导入"
        }
        return "拖放 CSV 文件到此处"
    }
    
    private var subtitleText: String {
        "支持 CSV、TSV 格式"
    }
    
    // MARK: - 支持的文件类型
    
    private var supportedTypes: [UTType] {
        [
            .commaSeparatedText,
            .tabSeparatedText,
            .plainText,
            .data
        ]
    }
    
    // MARK: - 处理拖放
    
    private func handleDrop(providers: [NSItemProvider]) {
        errorMessage = nil
        isProcessing = true
        
        var urls: [URL] = []
        let group = DispatchGroup()
        
        for provider in providers {
            if provider.hasItemConformingToTypeIdentifier(UTType.fileURL.identifier) {
                group.enter()
                provider.loadItem(forTypeIdentifier: UTType.fileURL.identifier) { item, error in
                    defer { group.leave() }
                    
                    if let data = item as? Data,
                       let url = URL(dataRepresentation: data, relativeTo: nil) {
                        // 检查文件扩展名
                        let ext = url.pathExtension.lowercased()
                        if ["csv", "tsv", "txt"].contains(ext) {
                            urls.append(url)
                        }
                    }
                }
            }
        }
        
        group.notify(queue: .main) {
            isProcessing = false
            
            if urls.isEmpty {
                errorMessage = "请拖放 CSV 或 TSV 文件"
            } else {
                onFilesDropped(urls)
            }
        }
    }
}

// MARK: - 预览

#if DEBUG
struct DropZoneView_Previews: PreviewProvider {
    static var previews: some View {
        DropZoneView { urls in
            print("Dropped: \(urls)")
        }
        .frame(width: 400, height: 250)
        .padding()
        .background(Color(red: 0.06, green: 0.06, blue: 0.10))
        .preferredColorScheme(.dark)
    }
}
#endif
