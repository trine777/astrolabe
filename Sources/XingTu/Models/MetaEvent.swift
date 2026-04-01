// 星图 (XingTu) - 元数据事件模型
// 归属: 影澜轩 (Yinglanxuan)

import Foundation

/// 影澜轩：元数据的变更事件流
public struct MetaEvent: Identifiable, Codable, Equatable {
    public let id: UUID
    public let timestamp: Date
    public let eventType: EventType
    public let objectId: UUID?                 // 相关对象
    public let propertyId: UUID?               // 相关属性（如适用）
    public let actorType: ActorType            // 操作者类型
    public let actorId: String?                // 操作者 ID
    public var beforeSnapshot: String?         // 变更前快照（JSON）
    public var afterSnapshot: String?          // 变更后快照（JSON）
    public var description: String?            // 变更说明
    
    // MARK: - 事件类型
    
    public enum EventType: String, Codable, CaseIterable {
        // 对象级别
        case objectCreated = "objectCreated"
        case objectUpdated = "objectUpdated"
        case objectConfirmed = "objectConfirmed"
        case objectPublished = "objectPublished"
        case objectArchived = "objectArchived"
        case objectDeleted = "objectDeleted"
        
        // 属性级别
        case propertyAdded = "propertyAdded"
        case propertyUpdated = "propertyUpdated"
        case propertyRemoved = "propertyRemoved"
        
        // 关系级别
        case relationCreated = "relationCreated"
        case relationConfirmed = "relationConfirmed"
        case relationRemoved = "relationRemoved"
        
        // 批量操作
        case bulkImport = "bulkImport"
        case bulkUpdate = "bulkUpdate"
        
        public var displayName: String {
            switch self {
            case .objectCreated: return "对象创建"
            case .objectUpdated: return "对象更新"
            case .objectConfirmed: return "对象确认"
            case .objectPublished: return "对象发布"
            case .objectArchived: return "对象归档"
            case .objectDeleted: return "对象删除"
            case .propertyAdded: return "属性添加"
            case .propertyUpdated: return "属性更新"
            case .propertyRemoved: return "属性移除"
            case .relationCreated: return "关系创建"
            case .relationConfirmed: return "关系确认"
            case .relationRemoved: return "关系移除"
            case .bulkImport: return "批量导入"
            case .bulkUpdate: return "批量更新"
            }
        }
        
        public var icon: String {
            switch self {
            case .objectCreated: return "plus.circle"
            case .objectUpdated: return "pencil.circle"
            case .objectConfirmed: return "checkmark.circle"
            case .objectPublished: return "arrow.up.circle"
            case .objectArchived: return "archivebox"
            case .objectDeleted: return "trash"
            case .propertyAdded: return "plus.square"
            case .propertyUpdated: return "pencil"
            case .propertyRemoved: return "minus.square"
            case .relationCreated: return "link"
            case .relationConfirmed: return "link.badge.plus"
            case .relationRemoved: return "link.badge.minus"
            case .bulkImport: return "square.and.arrow.down"
            case .bulkUpdate: return "arrow.triangle.2.circlepath"
            }
        }
        
        public var category: EventCategory {
            switch self {
            case .objectCreated, .objectUpdated, .objectConfirmed,
                 .objectPublished, .objectArchived, .objectDeleted:
                return .object
            case .propertyAdded, .propertyUpdated, .propertyRemoved:
                return .property
            case .relationCreated, .relationConfirmed, .relationRemoved:
                return .relation
            case .bulkImport, .bulkUpdate:
                return .bulk
            }
        }
    }
    
    public enum EventCategory: String, Codable {
        case object = "object"
        case property = "property"
        case relation = "relation"
        case bulk = "bulk"
    }
    
    // MARK: - 操作者类型
    
    public enum ActorType: String, Codable, CaseIterable {
        case user = "user"          // 用户操作
        case ai = "ai"              // AI 推断
        case system = "system"      // 系统自动
        
        public var displayName: String {
            switch self {
            case .user: return "用户"
            case .ai: return "AI"
            case .system: return "系统"
            }
        }
        
        public var icon: String {
            switch self {
            case .user: return "person"
            case .ai: return "brain"
            case .system: return "gearshape"
            }
        }
    }
    
    // MARK: - 初始化
    
    public init(
        id: UUID = UUID(),
        timestamp: Date = Date(),
        eventType: EventType,
        objectId: UUID? = nil,
        propertyId: UUID? = nil,
        actorType: ActorType,
        actorId: String? = nil,
        beforeSnapshot: String? = nil,
        afterSnapshot: String? = nil,
        description: String? = nil
    ) {
        self.id = id
        self.timestamp = timestamp
        self.eventType = eventType
        self.objectId = objectId
        self.propertyId = propertyId
        self.actorType = actorType
        self.actorId = actorId
        self.beforeSnapshot = beforeSnapshot
        self.afterSnapshot = afterSnapshot
        self.description = description
    }
    
    // MARK: - 便捷构造器
    
    /// 创建对象创建事件
    public static func objectCreated(
        objectId: UUID,
        by actor: ActorType,
        actorId: String? = nil,
        description: String? = nil
    ) -> MetaEvent {
        MetaEvent(
            eventType: .objectCreated,
            objectId: objectId,
            actorType: actor,
            actorId: actorId,
            description: description
        )
    }
    
    /// 创建对象确认事件
    public static func objectConfirmed(
        objectId: UUID,
        by userId: String? = nil
    ) -> MetaEvent {
        MetaEvent(
            eventType: .objectConfirmed,
            objectId: objectId,
            actorType: .user,
            actorId: userId,
            description: "用户确认元数据"
        )
    }
    
    /// 创建属性更新事件
    public static func propertyUpdated(
        objectId: UUID,
        propertyId: UUID,
        by actor: ActorType,
        before: String? = nil,
        after: String? = nil
    ) -> MetaEvent {
        MetaEvent(
            eventType: .propertyUpdated,
            objectId: objectId,
            propertyId: propertyId,
            actorType: actor,
            beforeSnapshot: before,
            afterSnapshot: after
        )
    }
}
