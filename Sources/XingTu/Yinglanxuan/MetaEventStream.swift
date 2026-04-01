// 星图 (XingTu) - 元数据事件流
// 归属: 影澜轩 (Yinglanxuan)

import Foundation
import Combine
import SQLite

/// 影澜轩：事件流协议
public protocol EventStreamProtocol {
    /// 发送事件
    func emit(_ event: MetaEvent) async
    
    /// 订阅事件
    func subscribe(filter: EventFilter?) -> AnyPublisher<MetaEvent, Never>
    
    /// 获取历史事件
    func getHistory(filter: EventFilter?, limit: Int) async throws -> [MetaEvent]
    
    /// 获取对象的变更历史
    func getObjectHistory(objectId: UUID) async throws -> [MetaEvent]
}

/// 事件过滤器
public struct EventFilter {
    public var eventTypes: [MetaEvent.EventType]?
    public var objectId: UUID?
    public var actorType: MetaEvent.ActorType?
    public var since: Date?
    
    public init(
        eventTypes: [MetaEvent.EventType]? = nil,
        objectId: UUID? = nil,
        actorType: MetaEvent.ActorType? = nil,
        since: Date? = nil
    ) {
        self.eventTypes = eventTypes
        self.objectId = objectId
        self.actorType = actorType
        self.since = since
    }
}

/// 影澜轩：元数据事件流实现
public class MetaEventStream: EventStreamProtocol {
    
    // MARK: - 属性
    
    private let sqliteManager: SQLiteManager
    private let eventSubject = PassthroughSubject<MetaEvent, Never>()
    
    // MARK: - 初始化
    
    public init(sqliteManager: SQLiteManager = .shared) {
        self.sqliteManager = sqliteManager
    }
    
    // MARK: - 发送事件
    
    public func emit(_ event: MetaEvent) async {
        // 持久化到数据库
        do {
            try await saveEvent(event)
        } catch {
            print("Failed to save event: \(error)")
        }
        
        // 发布到订阅者
        eventSubject.send(event)
    }
    
    // MARK: - 订阅事件
    
    public func subscribe(filter: EventFilter?) -> AnyPublisher<MetaEvent, Never> {
        guard let filter = filter else {
            return eventSubject.eraseToAnyPublisher()
        }
        
        return eventSubject
            .filter { event in
                // 过滤事件类型
                if let types = filter.eventTypes, !types.contains(event.eventType) {
                    return false
                }
                // 过滤对象 ID
                if let objectId = filter.objectId, event.objectId != objectId {
                    return false
                }
                // 过滤操作者类型
                if let actorType = filter.actorType, event.actorType != actorType {
                    return false
                }
                // 过滤时间
                if let since = filter.since, event.timestamp < since {
                    return false
                }
                return true
            }
            .eraseToAnyPublisher()
    }
    
    // MARK: - 获取历史
    
    public func getHistory(filter: EventFilter?, limit: Int) async throws -> [MetaEvent] {
        let db = try sqliteManager.getConnection()
        
        var query = SQLiteManager.metaEvents.order(SQLiteManager.evtTimestamp.desc)
        
        if let filter = filter {
            if let objectId = filter.objectId {
                query = query.filter(SQLiteManager.evtObjectId == objectId.uuidString)
            }
            if let actorType = filter.actorType {
                query = query.filter(SQLiteManager.evtActorType == actorType.rawValue)
            }
            if let since = filter.since {
                query = query.filter(SQLiteManager.evtTimestamp >= since)
            }
            if let eventTypes = filter.eventTypes, !eventTypes.isEmpty {
                let typeStrings = eventTypes.map { $0.rawValue }
                query = query.filter(typeStrings.contains(SQLiteManager.evtType))
            }
        }
        
        query = query.limit(limit)
        
        var events: [MetaEvent] = []
        for row in try db.prepare(query) {
            if let event = try? parseEventRow(row) {
                events.append(event)
            }
        }
        
        return events
    }
    
    public func getObjectHistory(objectId: UUID) async throws -> [MetaEvent] {
        return try await getHistory(
            filter: EventFilter(objectId: objectId),
            limit: 100
        )
    }
    
    // MARK: - 便捷方法
    
    /// 发送对象创建事件
    public func emitObjectCreated(
        objectId: UUID,
        by actor: MetaEvent.ActorType,
        actorId: String? = nil,
        description: String? = nil
    ) async {
        let event = MetaEvent.objectCreated(
            objectId: objectId,
            by: actor,
            actorId: actorId,
            description: description
        )
        await emit(event)
    }
    
    /// 发送对象确认事件
    public func emitObjectConfirmed(
        objectId: UUID,
        by userId: String? = nil
    ) async {
        let event = MetaEvent.objectConfirmed(
            objectId: objectId,
            by: userId
        )
        await emit(event)
    }
    
    /// 发送属性更新事件
    public func emitPropertyUpdated(
        objectId: UUID,
        propertyId: UUID,
        by actor: MetaEvent.ActorType,
        before: String? = nil,
        after: String? = nil
    ) async {
        let event = MetaEvent.propertyUpdated(
            objectId: objectId,
            propertyId: propertyId,
            by: actor,
            before: before,
            after: after
        )
        await emit(event)
    }
    
    // MARK: - 私有方法
    
    private func saveEvent(_ event: MetaEvent) async throws {
        let db = try sqliteManager.getConnection()
        
        let insert = SQLiteManager.metaEvents.insert(
            SQLiteManager.evtId <- event.id.uuidString,
            SQLiteManager.evtTimestamp <- event.timestamp,
            SQLiteManager.evtType <- event.eventType.rawValue,
            SQLiteManager.evtObjectId <- event.objectId?.uuidString,
            SQLiteManager.evtPropertyId <- event.propertyId?.uuidString,
            SQLiteManager.evtActorType <- event.actorType.rawValue,
            SQLiteManager.evtActorId <- event.actorId,
            SQLiteManager.evtBeforeSnapshot <- event.beforeSnapshot,
            SQLiteManager.evtAfterSnapshot <- event.afterSnapshot,
            SQLiteManager.evtDescription <- event.description
        )
        
        try db.run(insert)
    }
    
    private func parseEventRow(_ row: Row) throws -> MetaEvent {
        let id = UUID(uuidString: row[SQLiteManager.evtId])!
        
        return MetaEvent(
            id: id,
            timestamp: row[SQLiteManager.evtTimestamp],
            eventType: MetaEvent.EventType(rawValue: row[SQLiteManager.evtType]) ?? .objectUpdated,
            objectId: row[SQLiteManager.evtObjectId].flatMap { UUID(uuidString: $0) },
            propertyId: row[SQLiteManager.evtPropertyId].flatMap { UUID(uuidString: $0) },
            actorType: MetaEvent.ActorType(rawValue: row[SQLiteManager.evtActorType]) ?? .system,
            actorId: row[SQLiteManager.evtActorId],
            beforeSnapshot: row[SQLiteManager.evtBeforeSnapshot],
            afterSnapshot: row[SQLiteManager.evtAfterSnapshot],
            description: row[SQLiteManager.evtDescription]
        )
    }
}
