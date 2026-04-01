// 星图 - 世界模型视图

import SwiftUI
import XingTu

struct WorldModelView: View {
    @EnvironmentObject var appState: AppState
    @State private var context: WorldModelContext?
    @State private var isLoading = true
    
    var body: some View {
        VStack(spacing: 0) {
            // 头部
            HStack {
                VStack(alignment: .leading) {
                    Text("世界模型")
                        .font(.title2)
                        .fontWeight(.bold)
                    
                    Text("数据世界的语义视图 - 由星空座维护")
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                Button(action: refresh) {
                    Label("刷新", systemImage: "arrow.clockwise")
                }
            }
            .padding()
            
            Divider()
            
            if isLoading {
                ProgressView()
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if let ctx = context {
                if ctx.objects.isEmpty {
                    EmptyWorldModelView()
                } else {
                    WorldModelContent(context: ctx)
                }
            }
        }
        .task {
            await loadContext()
        }
    }
    
    private func loadContext() async {
        isLoading = true
        do {
            context = try await appState.service.getWorldModelContext()
        } catch {
            appState.errorMessage = error.localizedDescription
        }
        isLoading = false
    }
    
    private func refresh() {
        Task {
            await loadContext()
        }
    }
}

// MARK: - 世界模型内容

struct WorldModelContent: View {
    let context: WorldModelContext
    
    @State private var selectedTab = 0
    
    var body: some View {
        VStack(spacing: 0) {
            // 统计卡片
            HStack(spacing: 16) {
                StatCard(
                    title: "数据对象",
                    value: "\(context.objects.count)",
                    icon: "cylinder.split.1x2",
                    color: .blue
                )
                
                StatCard(
                    title: "数据关系",
                    value: "\(context.relations.count)",
                    icon: "link",
                    color: .purple
                )
                
                StatCard(
                    title: "业务指标",
                    value: "\(context.metrics.count)",
                    icon: "chart.bar",
                    color: .green
                )
            }
            .padding()
            
            // 标签页
            Picker("", selection: $selectedTab) {
                Text("对象").tag(0)
                Text("关系").tag(1)
                Text("指标").tag(2)
                Text("AI 上下文").tag(3)
            }
            .pickerStyle(.segmented)
            .padding(.horizontal)
            
            // 内容
            TabView(selection: $selectedTab) {
                ObjectsListView(objects: context.objects)
                    .tag(0)
                
                RelationsListView(relations: context.relations)
                    .tag(1)
                
                MetricsListView(metrics: context.metrics)
                    .tag(2)
                
                AIContextView(context: context)
                    .tag(3)
            }
            .tabViewStyle(.automatic)
        }
    }
}

// MARK: - 统计卡片

struct StatCard: View {
    let title: String
    let value: String
    let icon: String
    let color: Color
    
    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.title)
                .foregroundColor(color)
                .frame(width: 40)
            
            VStack(alignment: .leading) {
                Text(value)
                    .font(.title2)
                    .fontWeight(.bold)
                Text(title)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(color.opacity(0.1))
        .cornerRadius(12)
    }
}

// MARK: - 对象列表视图

struct ObjectsListView: View {
    let objects: [MetaObjectSummary]
    
    var body: some View {
        List {
            ForEach(objects, id: \.id) { obj in
                HStack(spacing: 12) {
                    Image(systemName: "cylinder")
                        .foregroundColor(.blue)
                    
                    VStack(alignment: .leading, spacing: 4) {
                        Text(obj.name)
                            .fontWeight(.medium)
                        
                        HStack {
                            Text(obj.objectType)
                                .font(.caption)
                                .padding(.horizontal, 6)
                                .padding(.vertical, 2)
                                .background(Color.blue.opacity(0.2))
                                .cornerRadius(4)
                            
                            if let rows = obj.rowCount {
                                Text("\(rows) 行")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }
                        
                        if let desc = obj.description {
                            Text(desc)
                                .font(.caption)
                                .foregroundColor(.secondary)
                                .lineLimit(2)
                        }
                    }
                    
                    Spacer()
                    
                    Text(obj.status)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .padding(.vertical, 4)
            }
        }
    }
}

// MARK: - 关系列表视图

struct RelationsListView: View {
    let relations: [MetaRelationSummary]
    
    var body: some View {
        if relations.isEmpty {
            VStack(spacing: 16) {
                Image(systemName: "link.badge.plus")
                    .font(.system(size: 48))
                    .foregroundColor(.secondary)
                
                Text("暂无数据关系")
                    .font(.title3)
                
                Text("当 AI 分析发现数据间的关联时，关系将显示在这里")
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        } else {
            List {
                ForEach(relations, id: \.id) { rel in
                    HStack {
                        Text(rel.relationName ?? "未命名关系")
                            .fontWeight(.medium)
                        
                        Image(systemName: "arrow.right")
                            .foregroundColor(.secondary)
                        
                        Text(rel.relationType)
                            .font(.caption)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Color.purple.opacity(0.2))
                            .cornerRadius(4)
                        
                        Spacer()
                        
                        if rel.isConfirmed {
                            Image(systemName: "checkmark.circle.fill")
                                .foregroundColor(.green)
                        }
                    }
                }
            }
        }
    }
}

// MARK: - 指标列表视图

struct MetricsListView: View {
    let metrics: [MetricDefSummary]
    
    var body: some View {
        if metrics.isEmpty {
            VStack(spacing: 16) {
                Image(systemName: "chart.bar.doc.horizontal")
                    .font(.system(size: 48))
                    .foregroundColor(.secondary)
                
                Text("暂无业务指标")
                    .font(.title3)
                
                Text("定义业务指标后将显示在这里")
                    .foregroundColor(.secondary)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        } else {
            List {
                ForEach(metrics, id: \.id) { metric in
                    VStack(alignment: .leading, spacing: 4) {
                        HStack {
                            Text(metric.displayName)
                                .fontWeight(.medium)
                            
                            if let unit = metric.unit {
                                Text("(\(unit))")
                                    .foregroundColor(.secondary)
                            }
                        }
                        
                        Text(metric.name)
                            .font(.system(.caption, design: .monospaced))
                            .foregroundColor(.secondary)
                        
                        if let desc = metric.description {
                            Text(desc)
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                }
            }
        }
    }
}

// MARK: - AI 上下文视图

struct AIContextView: View {
    let context: WorldModelContext
    
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("AI 可读上下文")
                    .font(.headline)
                
                Text("以下是生成给 AI 的世界模型上下文，用于语义理解和 NL-to-SQL 翻译：")
                    .foregroundColor(.secondary)
                
                Text(context.toPromptContext())
                    .font(.system(.body, design: .monospaced))
                    .padding()
                    .background(Color.secondary.opacity(0.1))
                    .cornerRadius(8)
            }
            .padding()
        }
    }
}

// MARK: - 空世界模型视图

struct EmptyWorldModelView: View {
    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "globe")
                .font(.system(size: 64))
                .foregroundColor(.secondary)
            
            Text("世界模型为空")
                .font(.title2)
                .fontWeight(.medium)
            
            Text("导入并发布数据源后，世界模型将在此展示")
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
            
            VStack(alignment: .leading, spacing: 8) {
                Label("导入 CSV 文件", systemImage: "1.circle")
                Label("确认元数据", systemImage: "2.circle")
                Label("发布数据源", systemImage: "3.circle")
            }
            .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
