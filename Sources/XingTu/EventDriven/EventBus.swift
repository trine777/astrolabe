// EventBus.swift
// 星图 - 事件总线
// 版本: v0.2.0

import Foundation
import Combine
import SQLite

// MARK: - 事件总线协议

/// 事件总线协议
public protocol EventBusProtocol {
    /// 发布事件
    func publish<E: EventProtocol>(_ event: E) async
    
    /// 订阅事件类型
    func subscribe(to types: [EventType], handler: @escaping (any EventProtocol) async -> Void) async -> UUID
    
    /// 订阅所有事件
    func subscribeAll(handler: @escaping (any EventProtocol) async -> Void) async -> UUID
    
    /// 取消订阅
    func unsubscribe(_ subscriptionId: UUID) async
    
    /// 获取事件历史
    func getHistory(types: [EventType]?, limit: Int) async -> [any EventProtocol]
}

// MARK: - 事件订阅

/// 事件订阅信息
private struct Subscription {
    let id: UUID
    let types: [EventType]?  // nil 表示订阅所有
    let handler: (any EventProtocol) async -> Void
}

// MARK: - 事件总线实现

/// 事件总线 - 影澜轩核心组件
public actor EventBus: EventBusProtocol {
    
    // MARK: - 单例
    
    public static let shared = EventBus()
    
    // MARK: - 属性
    
    private var subscriptions: [UUID: Subscription] = [:]
    private var eventHistory: [any EventProtocol] = []
    private let maxHistorySize: Int = 1000
    
    // SQLite 持久化（可选）
    private var sqliteManager: SQLiteManager?
    
    // MARK: - 初始化
    
    public init(sqliteManager: SQLiteManager? = nil) {
        self.sqliteManager = sqliteManager
    }
    
    // MARK: - 发布事件
    
    /// 发布事件
    public func publish<E: EventProtocol>(_ event: E) async {
        // 1. 记录到历史
        eventHistory.append(event)
        if eventHistory.count > maxHistorySize {
            eventHistory.removeFirst(eventHistory.count - maxHistorySize)
        }
        
        // 2. 持久化到数据库（可选）
        if let db = sqliteManager {
            await persistEvent(event, to: db)
        }
        
        // 3. 通知所有匹配的订阅者
        let matchingSubscriptions = subscriptions.values.filter { subscription in
            subscription.types == nil || subscription.types!.contains(event.type)
        }
        
        for subscription in matchingSubscriptions {
            await subscription.handler(event)
        }
        
        // 4. 打印日志（调试用）
        #if DEBUG
        print("📣 [EventBus] \(event.type.rawValue) from \(event.source)")
        #endif
    }
    
    // MARK: - 订阅
    
    /// 订阅指定类型的事件
    public func subscribe(
        to types: [EventType],
        handler: @escaping (any EventProtocol) async -> Void
    ) -> UUID {
        let subscriptionId = UUID()
        let subscription = Subscription(id: subscriptionId, types: types, handler: handler)
        subscriptions[subscriptionId] = subscription
        return subscriptionId
    }
    
    /// 订阅所有事件
    public func subscribeAll(
        handler: @escaping (any EventProtocol) async -> Void
    ) -> UUID {
        let subscriptionId = UUID()
        let subscription = Subscription(id: subscriptionId, types: nil, handler: handler)
        subscriptions[subscriptionId] = subscription
        return subscriptionId
    }
    
    /// 取消订阅
    public func unsubscribe(_ subscriptionId: UUID) {
        subscriptions.removeValue(forKey: subscriptionId)
    }
    
    // MARK: - 历史查询
    
    /// 获取事件历史
    public func getHistory(types: [EventType]? = nil, limit: Int = 100) async -> [any EventProtocol] {
        var result = eventHistory
        
        if let types = types {
            result = result.filter { types.contains($0.type) }
        }
        
        return Array(result.suffix(limit))
    }
    
    /// 获取关联事件链
    public func getCorrelatedEvents(correlationId: UUID) async -> [any EventProtocol] {
        return eventHistory.filter { $0.correlationId == correlationId }
    }
    
    // MARK: - 持久化
    
    private func persistEvent<E: EventProtocol>(_ event: E, to db: SQLiteManager) async {
        do {
            let connection = try db.getConnection()

            let encoder = JSONEncoder()
            let payloadData = try encoder.encode(event)
            let payloadString = String(data: payloadData, encoding: .utf8) ?? "{}"

            // 写入 v2 events 表（事件总线完整记录）
            let insertV2 = SQLiteManager.events.insert(
                SQLiteManager.evtV2Id <- event.id.uuidString,
                SQLiteManager.evtV2EventType <- event.type.rawValue,
                SQLiteManager.evtV2Source <- event.source,
                SQLiteManager.evtV2CorrelationId <- event.correlationId?.uuidString,
                SQLiteManager.evtV2Payload <- payloadString,
                SQLiteManager.evtV2Timestamp <- ISO8601DateFormatter().string(from: event.timestamp),
                SQLiteManager.evtV2Processed <- 0
            )
            try connection.run(insertV2)

            // 同步写入 meta_events 表（审计兼容层）
            let insertV1 = SQLiteManager.metaEvents.insert(
                SQLiteManager.evtId <- event.id.uuidString,
                SQLiteManager.evtTimestamp <- event.timestamp,
                SQLiteManager.evtType <- event.type.rawValue,
                SQLiteManager.evtObjectId <- nil as String?,
                SQLiteManager.evtPropertyId <- nil as String?,
                SQLiteManager.evtActorType <- event.source,
                SQLiteManager.evtActorId <- nil as String?,
                SQLiteManager.evtBeforeSnapshot <- nil as String?,
                SQLiteManager.evtAfterSnapshot <- payloadString,
                SQLiteManager.evtDescription <- "EventBus: \(event.type.rawValue)"
            )
            try connection.run(insertV1)
        } catch {
            print("⚠️ [EventBus] 事件持久化失败: \(error)")
        }
    }
}

// MARK: - 便捷发布方法

extension EventBus {
    
    /// 发布文件拖入事件
    public func emitFileDropped(
        filePath: String,
        fileType: String,
        fileSize: Int,
        fileName: String
    ) async -> UUID {
        let event = FileDroppedEvent(
            filePath: filePath,
            fileType: fileType,
            fileSize: fileSize,
            fileName: fileName
        )
        await publish(event)
        return event.correlationId ?? event.id
    }
    
    /// 发布文件解析完成事件
    public func emitFileParsed(
        correlationId: UUID,
        objectId: UUID,
        columnCount: Int,
        rowCount: Int,
        encoding: String,
        parseDurationMs: Int
    ) async {
        let event = FileParsedEvent(
            correlationId: correlationId,
            objectId: objectId,
            columnCount: columnCount,
            rowCount: rowCount,
            encoding: encoding,
            parseDurationMs: parseDurationMs
        )
        await publish(event)
    }
    
    /// 发布对象创建事件
    public func emitObjectCreated(
        correlationId: UUID?,
        objectId: UUID,
        objectName: String,
        objectType: String,
        sourceFile: String?
    ) async {
        let event = ObjectCreatedEvent(
            correlationId: correlationId,
            objectId: objectId,
            objectName: objectName,
            objectType: objectType,
            sourceFile: sourceFile
        )
        await publish(event)
    }
    
    /// 发布属性就绪事件
    public func emitObjectPropertiesReady(
        correlationId: UUID?,
        objectId: UUID,
        propertyCount: Int,
        autoAppliedCount: Int,
        pendingReviewCount: Int
    ) async {
        let event = ObjectPropertiesReadyEvent(
            correlationId: correlationId,
            objectId: objectId,
            propertyCount: propertyCount,
            autoAppliedCount: autoAppliedCount,
            pendingReviewCount: pendingReviewCount
        )
        await publish(event)
    }
    
    /// 发布对象就绪事件
    public func emitObjectReady(
        correlationId: UUID?,
        objectId: UUID,
        objectName: String,
        totalProperties: Int,
        pendingReviews: Int,
        discoveredRelations: Int
    ) async {
        let event = ObjectReadyEvent(
            correlationId: correlationId,
            objectId: objectId,
            objectName: objectName,
            totalProperties: totalProperties,
            pendingReviews: pendingReviews,
            discoveredRelations: discoveredRelations
        )
        await publish(event)
    }
    
    /// 发布 AI 决策事件
    public func emitAIDecisionMade(
        correlationId: UUID?,
        decisionId: UUID,
        agentType: String,
        objectId: UUID,
        propertyId: UUID?,
        actionType: String,
        proposedValue: String,
        confidence: Double,
        reasoning: String
    ) async {
        let event = AIDecisionMadeEvent(
            source: "agent.\(agentType)",
            correlationId: correlationId,
            decisionId: decisionId,
            agentType: agentType,
            objectId: objectId,
            propertyId: propertyId,
            actionType: actionType,
            proposedValue: proposedValue,
            confidence: confidence,
            reasoning: reasoning
        )
        await publish(event)
    }
}

// MARK: - Combine 扩展

extension EventBus {
    
    /// 创建 Combine Publisher
    public nonisolated func publisher(for types: [EventType]) -> AnyPublisher<any EventProtocol, Never> {
        let subject = PassthroughSubject<any EventProtocol, Never>()
        
        Task {
            let _ = await self.subscribe(to: types) { event in
                subject.send(event)
            }
        }
        
        return subject.eraseToAnyPublisher()
    }
    
    /// 创建所有事件的 Publisher
    public nonisolated func allEventsPublisher() -> AnyPublisher<any EventProtocol, Never> {
        let subject = PassthroughSubject<any EventProtocol, Never>()
        
        Task {
            let _ = await self.subscribeAll { event in
                subject.send(event)
            }
        }
        
        return subject.eraseToAnyPublisher()
    }
}
