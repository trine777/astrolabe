// 星图 - 事件历史视图

import SwiftUI
import XingTu

struct EventHistoryView: View {
    @EnvironmentObject var appState: AppState
    
    @State private var events: [MetaEvent] = []
    @State private var isLoading = true
    @State private var filterType: MetaEvent.EventType?
    @State private var filterActor: MetaEvent.ActorType?
    
    private var filteredEvents: [MetaEvent] {
        var result = events
        
        if let type = filterType {
            result = result.filter { $0.eventType == type }
        }
        
        if let actor = filterActor {
            result = result.filter { $0.actorType == actor }
        }
        
        return result
    }
    
    var body: some View {
        VStack(spacing: 0) {
            // 头部
            HStack {
                VStack(alignment: .leading) {
                    Text("变更记录")
                        .font(.title2)
                        .fontWeight(.bold)
                    
                    Text("影澜轩事件流 - 记录所有元数据变更")
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                // 过滤器
                HStack(spacing: 12) {
                    Picker("类型", selection: $filterType) {
                        Text("所有类型").tag(nil as MetaEvent.EventType?)
                        ForEach(MetaEvent.EventType.allCases, id: \.self) { type in
                            Text(type.displayName).tag(type as MetaEvent.EventType?)
                        }
                    }
                    .frame(width: 140)
                    
                    Picker("操作者", selection: $filterActor) {
                        Text("所有").tag(nil as MetaEvent.ActorType?)
                        ForEach(MetaEvent.ActorType.allCases, id: \.self) { actor in
                            Text(actor.displayName).tag(actor as MetaEvent.ActorType?)
                        }
                    }
                    .frame(width: 100)
                }
                
                Button(action: refresh) {
                    Label("刷新", systemImage: "arrow.clockwise")
                }
            }
            .padding()
            
            Divider()
            
            // 事件列表
            if isLoading {
                ProgressView()
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if filteredEvents.isEmpty {
                EmptyEventsView()
            } else {
                EventsTimeline(events: filteredEvents)
            }
        }
        .task {
            await loadEvents()
        }
    }
    
    private func loadEvents() async {
        isLoading = true
        do {
            events = try await appState.service.eventStream.getHistory(filter: nil, limit: 200)
        } catch {
            appState.errorMessage = error.localizedDescription
        }
        isLoading = false
    }
    
    private func refresh() {
        Task {
            await loadEvents()
        }
    }
}

// MARK: - 事件时间线

struct EventsTimeline: View {
    let events: [MetaEvent]
    
    private var groupedEvents: [(String, [MetaEvent])] {
        let calendar = Calendar.current
        let grouped = Dictionary(grouping: events) { event in
            calendar.startOfDay(for: event.timestamp)
        }
        
        return grouped.sorted { $0.key > $1.key }.map { date, events in
            let formatter = DateFormatter()
            formatter.dateFormat = "yyyy年MM月dd日"
            return (formatter.string(from: date), events.sorted { $0.timestamp > $1.timestamp })
        }
    }
    
    var body: some View {
        List {
            ForEach(groupedEvents, id: \.0) { date, dayEvents in
                Section(header: Text(date).font(.headline)) {
                    ForEach(dayEvents) { event in
                        EventRow(event: event)
                    }
                }
            }
        }
        .listStyle(.inset)
    }
}

// MARK: - 事件行

struct EventRow: View {
    let event: MetaEvent
    
    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            // 时间线图标
            VStack {
                Circle()
                    .fill(eventColor)
                    .frame(width: 10, height: 10)
                
                Rectangle()
                    .fill(Color.secondary.opacity(0.3))
                    .frame(width: 2)
            }
            .frame(width: 10)
            
            // 内容
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Image(systemName: event.eventType.icon)
                        .foregroundColor(eventColor)
                    
                    Text(event.eventType.displayName)
                        .fontWeight(.medium)
                    
                    Spacer()
                    
                    Text(event.timestamp.formatted(date: .omitted, time: .shortened))
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                if let description = event.description {
                    Text(description)
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                
                // 操作者信息
                HStack(spacing: 8) {
                    Image(systemName: event.actorType.icon)
                    Text(event.actorType.displayName)
                    
                    if let actorId = event.actorId {
                        Text("·")
                        Text(actorId)
                    }
                }
                .font(.caption)
                .foregroundColor(.secondary)
                
                // 快照信息
                if event.beforeSnapshot != nil || event.afterSnapshot != nil {
                    HStack(spacing: 16) {
                        if let before = event.beforeSnapshot {
                            VStack(alignment: .leading) {
                                Text("变更前")
                                    .font(.caption2)
                                    .foregroundColor(.secondary)
                                Text(before)
                                    .font(.caption)
                                    .lineLimit(2)
                            }
                            .padding(8)
                            .background(Color.red.opacity(0.1))
                            .cornerRadius(6)
                        }
                        
                        if let after = event.afterSnapshot {
                            VStack(alignment: .leading) {
                                Text("变更后")
                                    .font(.caption2)
                                    .foregroundColor(.secondary)
                                Text(after)
                                    .font(.caption)
                                    .lineLimit(2)
                            }
                            .padding(8)
                            .background(Color.green.opacity(0.1))
                            .cornerRadius(6)
                        }
                    }
                }
            }
        }
        .padding(.vertical, 8)
    }
    
    private var eventColor: Color {
        switch event.eventType.category {
        case .object: return .blue
        case .property: return .purple
        case .relation: return .orange
        case .bulk: return .green
        }
    }
}

// MARK: - 空事件视图

struct EmptyEventsView: View {
    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "clock.arrow.circlepath")
                .font(.system(size: 64))
                .foregroundColor(.secondary)
            
            Text("暂无变更记录")
                .font(.title2)
                .fontWeight(.medium)
            
            Text("元数据的所有变更都将记录在这里")
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
