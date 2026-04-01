// Event.swift
// 星图 - 事件定义
// 版本: v0.2.0

import Foundation

// MARK: - 事件协议

/// 事件协议 - 所有事件类型必须遵循
public protocol EventProtocol: Codable, Sendable {
    var id: UUID { get }
    var type: EventType { get }
    var timestamp: Date { get }
    var source: String { get }
    var correlationId: UUID? { get }
}

// MARK: - 事件类型

/// 事件类型枚举
public enum EventType: String, Codable, CaseIterable, Sendable {
    // 文件事件
    case fileDropped = "file.dropped"
    case fileParsed = "file.parsed"
    case fileParseFailed = "file.parse_failed"
    
    // 对象事件
    case objectCreated = "object.created"
    case objectUpdated = "object.updated"
    case objectPropertiesReady = "object.properties_ready"
    case objectReady = "object.ready"
    case objectConfirmed = "object.confirmed"
    case objectArchived = "object.archived"
    
    // AI 决策事件
    case aiDecisionMade = "ai.decision_made"
    case aiDecisionApplied = "ai.decision_applied"
    case aiDecisionRejected = "ai.decision_rejected"
    case aiDecisionRolledBack = "ai.decision_rolled_back"
    
    // 审核事件
    case reviewCreated = "review.created"
    case reviewApproved = "review.approved"
    case reviewRejected = "review.rejected"
    case reviewModified = "review.modified"
    case reviewExpired = "review.expired"
    
    // 行技事件
    case xingjiStarted = "xingji.started"
    case xingjiCompleted = "xingji.completed"
    case xingjiFailed = "xingji.failed"
    
    // 通知事件
    case notifySent = "notify.sent"
    case notifyRead = "notify.read"
}

// MARK: - 通用事件

/// 通用事件结构
public struct Event: EventProtocol {
    public let id: UUID
    public let type: EventType
    public let timestamp: Date
    public let source: String
    public let correlationId: UUID?
    public let payload: [String: AnyCodable]
    
    public init(
        id: UUID = UUID(),
        type: EventType,
        source: String,
        correlationId: UUID? = nil,
        payload: [String: AnyCodable] = [:]
    ) {
        self.id = id
        self.type = type
        self.timestamp = Date()
        self.source = source
        self.correlationId = correlationId
        self.payload = payload
    }
    
    /// 获取 payload 中的值
    public func get<T>(_ key: String) -> T? {
        return payload[key]?.value as? T
    }
}

// MARK: - 具体事件类型

/// 文件拖入事件
public struct FileDroppedEvent: EventProtocol {
    public let id: UUID
    public let type: EventType = .fileDropped
    public let timestamp: Date
    public let source: String
    public let correlationId: UUID?
    
    // Payload
    public let filePath: String
    public let fileType: String
    public let fileSize: Int
    public let fileName: String
    
    public init(
        id: UUID = UUID(),
        source: String = "ui.drop_zone",
        correlationId: UUID? = nil,
        filePath: String,
        fileType: String,
        fileSize: Int,
        fileName: String
    ) {
        self.id = id
        self.timestamp = Date()
        self.source = source
        self.correlationId = correlationId ?? id  // 用自身 ID 作为 correlation ID
        self.filePath = filePath
        self.fileType = fileType
        self.fileSize = fileSize
        self.fileName = fileName
    }
}

/// 文件解析完成事件
public struct FileParsedEvent: EventProtocol {
    public let id: UUID
    public let type: EventType = .fileParsed
    public let timestamp: Date
    public let source: String
    public let correlationId: UUID?
    
    // Payload
    public let objectId: UUID
    public let columnCount: Int
    public let rowCount: Int
    public let encoding: String
    public let parseDurationMs: Int
    
    public init(
        id: UUID = UUID(),
        source: String = "csv_parse_cell",
        correlationId: UUID?,
        objectId: UUID,
        columnCount: Int,
        rowCount: Int,
        encoding: String,
        parseDurationMs: Int
    ) {
        self.id = id
        self.timestamp = Date()
        self.source = source
        self.correlationId = correlationId
        self.objectId = objectId
        self.columnCount = columnCount
        self.rowCount = rowCount
        self.encoding = encoding
        self.parseDurationMs = parseDurationMs
    }
}

/// 对象创建事件
public struct ObjectCreatedEvent: EventProtocol {
    public let id: UUID
    public let type: EventType = .objectCreated
    public let timestamp: Date
    public let source: String
    public let correlationId: UUID?
    
    // Payload
    public let objectId: UUID
    public let objectName: String
    public let objectType: String
    public let sourceFile: String?
    public let status: String
    
    public init(
        id: UUID = UUID(),
        source: String = "meta_store",
        correlationId: UUID?,
        objectId: UUID,
        objectName: String,
        objectType: String,
        sourceFile: String?,
        status: String = "draft"
    ) {
        self.id = id
        self.timestamp = Date()
        self.source = source
        self.correlationId = correlationId
        self.objectId = objectId
        self.objectName = objectName
        self.objectType = objectType
        self.sourceFile = sourceFile
        self.status = status
    }
}

/// 属性就绪事件
public struct ObjectPropertiesReadyEvent: EventProtocol {
    public let id: UUID
    public let type: EventType = .objectPropertiesReady
    public let timestamp: Date
    public let source: String
    public let correlationId: UUID?
    
    // Payload
    public let objectId: UUID
    public let propertyCount: Int
    public let autoAppliedCount: Int
    public let pendingReviewCount: Int
    
    public init(
        id: UUID = UUID(),
        source: String = "semantic_inference_agent",
        correlationId: UUID?,
        objectId: UUID,
        propertyCount: Int,
        autoAppliedCount: Int,
        pendingReviewCount: Int
    ) {
        self.id = id
        self.timestamp = Date()
        self.source = source
        self.correlationId = correlationId
        self.objectId = objectId
        self.propertyCount = propertyCount
        self.autoAppliedCount = autoAppliedCount
        self.pendingReviewCount = pendingReviewCount
    }
}

/// 对象就绪事件
public struct ObjectReadyEvent: EventProtocol {
    public let id: UUID
    public let type: EventType = .objectReady
    public let timestamp: Date
    public let source: String
    public let correlationId: UUID?
    
    // Payload
    public let objectId: UUID
    public let objectName: String
    public let totalProperties: Int
    public let pendingReviews: Int
    public let discoveredRelations: Int
    
    public init(
        id: UUID = UUID(),
        source: String = "xingji_scheduler",
        correlationId: UUID?,
        objectId: UUID,
        objectName: String,
        totalProperties: Int,
        pendingReviews: Int,
        discoveredRelations: Int
    ) {
        self.id = id
        self.timestamp = Date()
        self.source = source
        self.correlationId = correlationId
        self.objectId = objectId
        self.objectName = objectName
        self.totalProperties = totalProperties
        self.pendingReviews = pendingReviews
        self.discoveredRelations = discoveredRelations
    }
}

/// AI 决策事件
public struct AIDecisionMadeEvent: EventProtocol {
    public let id: UUID
    public let type: EventType = .aiDecisionMade
    public let timestamp: Date
    public let source: String
    public let correlationId: UUID?
    
    // Payload
    public let decisionId: UUID
    public let agentType: String
    public let objectId: UUID
    public let propertyId: UUID?
    public let actionType: String
    public let proposedValue: String
    public let confidence: Double
    public let reasoning: String
    
    public init(
        id: UUID = UUID(),
        source: String,
        correlationId: UUID?,
        decisionId: UUID,
        agentType: String,
        objectId: UUID,
        propertyId: UUID?,
        actionType: String,
        proposedValue: String,
        confidence: Double,
        reasoning: String
    ) {
        self.id = id
        self.timestamp = Date()
        self.source = source
        self.correlationId = correlationId
        self.decisionId = decisionId
        self.agentType = agentType
        self.objectId = objectId
        self.propertyId = propertyId
        self.actionType = actionType
        self.proposedValue = proposedValue
        self.confidence = confidence
        self.reasoning = reasoning
    }
}

/// 行技启动事件
public struct XingJiStartedEvent: EventProtocol {
    public let id: UUID
    public let type: EventType = .xingjiStarted
    public let timestamp: Date
    public let source: String
    public let correlationId: UUID?
    
    // Payload
    public let executionId: UUID
    public let xingjiId: String
    public let triggerEventId: UUID
    public let targetObjectId: UUID?
    
    public init(
        id: UUID = UUID(),
        source: String = "xingji_scheduler",
        correlationId: UUID?,
        executionId: UUID,
        xingjiId: String,
        triggerEventId: UUID,
        targetObjectId: UUID?
    ) {
        self.id = id
        self.timestamp = Date()
        self.source = source
        self.correlationId = correlationId
        self.executionId = executionId
        self.xingjiId = xingjiId
        self.triggerEventId = triggerEventId
        self.targetObjectId = targetObjectId
    }
}

// MARK: - AnyCodable 辅助类型

/// 通用 Codable 包装器
public struct AnyCodable: Codable, Sendable {
    public let value: Any
    
    public init(_ value: Any) {
        self.value = value
    }
    
    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        
        if let bool = try? container.decode(Bool.self) {
            value = bool
        } else if let int = try? container.decode(Int.self) {
            value = int
        } else if let double = try? container.decode(Double.self) {
            value = double
        } else if let string = try? container.decode(String.self) {
            value = string
        } else if let array = try? container.decode([AnyCodable].self) {
            value = array.map { $0.value }
        } else if let dict = try? container.decode([String: AnyCodable].self) {
            value = dict.mapValues { $0.value }
        } else {
            value = NSNull()
        }
    }
    
    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        
        switch value {
        case let bool as Bool:
            try container.encode(bool)
        case let int as Int:
            try container.encode(int)
        case let double as Double:
            try container.encode(double)
        case let string as String:
            try container.encode(string)
        case let array as [Any]:
            try container.encode(array.map { AnyCodable($0) })
        case let dict as [String: Any]:
            try container.encode(dict.mapValues { AnyCodable($0) })
        default:
            try container.encodeNil()
        }
    }
}
