// AIDecision.swift
// 星图 - AI 决策模型
// 版本: v0.2.0

import Foundation

// MARK: - AI 决策

/// AI 决策 - 记录 AI 的每个决策
public struct AIDecision: Identifiable, Codable, Sendable {
    public let id: UUID
    public let agentType: String
    public let objectId: UUID
    public let propertyId: UUID?
    public let relationId: UUID?
    
    public let actionType: ActionType
    public var proposedValue: DecisionValue
    public let previousValue: DecisionValue?
    
    public let confidence: Double
    public let reasoning: String
    
    public var status: DecisionStatus
    public var wasAutoApplied: Bool
    
    public let createdAt: Date
    public var appliedAt: Date?
    public var reviewedBy: String?
    public var reviewedAt: Date?
    
    public init(
        id: UUID = UUID(),
        agentType: String,
        objectId: UUID,
        propertyId: UUID? = nil,
        relationId: UUID? = nil,
        actionType: ActionType,
        proposedValue: DecisionValue,
        previousValue: DecisionValue? = nil,
        confidence: Double,
        reasoning: String,
        status: DecisionStatus = .pending
    ) {
        self.id = id
        self.agentType = agentType
        self.objectId = objectId
        self.propertyId = propertyId
        self.relationId = relationId
        self.actionType = actionType
        self.proposedValue = proposedValue
        self.previousValue = previousValue
        self.confidence = confidence
        self.reasoning = reasoning
        self.status = status
        self.wasAutoApplied = false
        self.createdAt = Date()
    }
    
    /// 获取建议值的字符串表示
    public var proposedValueString: String {
        switch proposedValue {
        case .string(let s): return s
        case .semanticType(let t): return t.rawValue
        case .boolean(let b): return b ? "true" : "false"
        case .number(let n): return String(n)
        }
    }
}

// MARK: - 决策动作类型

public enum ActionType: String, Codable, Sendable {
    // 属性级操作
    case rename = "rename"
    case setSemanticType = "set_semantic_type"
    case setDescription = "set_description"
    case setUnit = "set_unit"
    case setFormat = "set_format"
    case setVisualPreference = "set_visual_preference"
    
    // 关系级操作
    case createRelation = "create_relation"
    case updateRelation = "update_relation"
    case removeRelation = "remove_relation"
    
    // 对象级操作
    case renameObject = "rename_object"
    case setObjectDescription = "set_object_description"
    case addTag = "add_tag"
}

// MARK: - 决策值

public enum DecisionValue: Codable, Sendable {
    case string(String)
    case semanticType(MetaProperty.SemanticType)
    case boolean(Bool)
    case number(Double)
    
    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        
        if let str = try? container.decode(String.self) {
            // 尝试解析为 SemanticType
            if let type = MetaProperty.SemanticType(rawValue: str) {
                self = .semanticType(type)
            } else {
                self = .string(str)
            }
        } else if let bool = try? container.decode(Bool.self) {
            self = .boolean(bool)
        } else if let num = try? container.decode(Double.self) {
            self = .number(num)
        } else {
            throw DecodingError.dataCorrupted(
                DecodingError.Context(codingPath: decoder.codingPath, debugDescription: "无法解码 DecisionValue")
            )
        }
    }
    
    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let s): try container.encode(s)
        case .semanticType(let t): try container.encode(t.rawValue)
        case .boolean(let b): try container.encode(b)
        case .number(let n): try container.encode(n)
        }
    }
}

// MARK: - 决策状态

public enum DecisionStatus: String, Codable, Sendable {
    case pending = "pending"
    case applied = "applied"
    case rejected = "rejected"
    case rolledBack = "rolled_back"
}

// MARK: - 决策处理结果

public struct DecisionProcessResult: Sendable {
    public let applied: Bool
    public let queued: Bool
    public let error: String?
    
    public init(applied: Bool, queued: Bool, error: String? = nil) {
        self.applied = applied
        self.queued = queued
        self.error = error
    }
}
