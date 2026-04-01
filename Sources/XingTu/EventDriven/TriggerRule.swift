// TriggerRule.swift
// 星图 - 触发规则
// 版本: v0.2.0

import Foundation

// MARK: - 触发规则

/// 触发规则 - 定义事件到行技的映射
public struct TriggerRule: Codable, Identifiable, Sendable {
    public let id: String
    public let name: String
    public let description: String?
    
    /// 触发事件类型
    public let eventType: EventType
    
    /// 触发条件（JSON 表达式）
    public let condition: TriggerCondition?
    
    /// 触发动作
    public let action: TriggerAction
    
    /// 优先级
    public let priority: Priority
    
    /// 延迟执行（毫秒）
    public let delayMs: Int
    
    /// 批量窗口（毫秒，合并同类事件）
    public let batchWindowMs: Int?
    
    /// 是否启用
    public let enabled: Bool
    
    public init(
        id: String,
        name: String,
        description: String? = nil,
        eventType: EventType,
        condition: TriggerCondition? = nil,
        action: TriggerAction,
        priority: Priority = .medium,
        delayMs: Int = 0,
        batchWindowMs: Int? = nil,
        enabled: Bool = true
    ) {
        self.id = id
        self.name = name
        self.description = description
        self.eventType = eventType
        self.condition = condition
        self.action = action
        self.priority = priority
        self.delayMs = delayMs
        self.batchWindowMs = batchWindowMs
        self.enabled = enabled
    }
}

// MARK: - 优先级

public enum Priority: String, Codable, Comparable, Sendable {
    case high
    case medium
    case low
    
    public static func < (lhs: Priority, rhs: Priority) -> Bool {
        let order: [Priority] = [.low, .medium, .high]
        return order.firstIndex(of: lhs)! < order.firstIndex(of: rhs)!
    }
}

// MARK: - 触发条件

/// 触发条件
public struct TriggerCondition: Codable, Sendable {
    public let op: ConditionOperator
    public let field: String
    public let value: AnyCodable?
    public let values: [AnyCodable]?
    
    public init(op: ConditionOperator, field: String, value: AnyCodable? = nil, values: [AnyCodable]? = nil) {
        self.op = op
        self.field = field
        self.value = value
        self.values = values
    }
    
    /// 评估条件
    public func evaluate(payload: [String: Any]) -> Bool {
        guard let fieldValue = getNestedValue(payload, path: field) else {
            return false
        }
        
        switch op {
        case .eq:
            return isEqual(fieldValue, value?.value)
        case .neq:
            return !isEqual(fieldValue, value?.value)
        case .gt:
            return compare(fieldValue, value?.value) > 0
        case .gte:
            return compare(fieldValue, value?.value) >= 0
        case .lt:
            return compare(fieldValue, value?.value) < 0
        case .lte:
            return compare(fieldValue, value?.value) <= 0
        case .in_:
            guard let vals = values else { return false }
            return vals.contains { isEqual(fieldValue, $0.value) }
        case .notIn:
            guard let vals = values else { return true }
            return !vals.contains { isEqual(fieldValue, $0.value) }
        case .contains:
            guard let str = fieldValue as? String, let search = value?.value as? String else { return false }
            return str.contains(search)
        case .exists:
            return true
        }
    }
    
    private func getNestedValue(_ dict: [String: Any], path: String) -> Any? {
        let keys = path.split(separator: ".").map(String.init)
        var current: Any = dict
        
        for key in keys {
            if let dict = current as? [String: Any], let value = dict[key] {
                current = value
            } else {
                return nil
            }
        }
        
        return current
    }
    
    private func isEqual(_ a: Any?, _ b: Any?) -> Bool {
        switch (a, b) {
        case let (a as String, b as String): return a == b
        case let (a as Int, b as Int): return a == b
        case let (a as Double, b as Double): return a == b
        case let (a as Bool, b as Bool): return a == b
        default: return false
        }
    }
    
    private func compare(_ a: Any?, _ b: Any?) -> Int {
        switch (a, b) {
        case let (a as Int, b as Int): return a < b ? -1 : (a > b ? 1 : 0)
        case let (a as Double, b as Double): return a < b ? -1 : (a > b ? 1 : 0)
        case let (a as String, b as String): return a < b ? -1 : (a > b ? 1 : 0)
        default: return 0
        }
    }
}

public enum ConditionOperator: String, Codable, Sendable {
    case eq = "eq"
    case neq = "neq"
    case gt = "gt"
    case gte = "gte"
    case lt = "lt"
    case lte = "lte"
    case in_ = "in"
    case notIn = "not_in"
    case contains = "contains"
    case exists = "exists"
}

// MARK: - 触发动作

/// 触发动作
public struct TriggerAction: Codable, Sendable {
    public let type: TriggerActionType
    public let params: [String: AnyCodable]
    
    public init(type: TriggerActionType, params: [String: AnyCodable] = [:]) {
        self.type = type
        self.params = params
    }
    
    /// 获取行技 ID
    public var xingjiId: String? {
        return params["xingji_id"]?.value as? String
    }
}

public enum TriggerActionType: String, Codable, Sendable {
    case startXingji = "start_xingji"
    case addToReviewQueue = "add_to_review_queue"
    case notify = "notify"
    case log = "log"
}

// MARK: - 预置规则

extension TriggerRule {
    
    /// 默认规则集
    public static let defaultRules: [TriggerRule] = [
        // 文件自动导入
        TriggerRule(
            id: "rule_auto_import",
            name: "文件自动导入",
            description: "文件拖入后自动启动导入行技",
            eventType: .fileDropped,
            condition: TriggerCondition(
                op: .in_,
                field: "fileType",
                values: [AnyCodable("csv"), AnyCodable("xlsx"), AnyCodable("json")]
            ),
            action: TriggerAction(
                type: .startXingji,
                params: ["xingji_id": AnyCodable("xingji.auto_import")]
            ),
            priority: .high
        ),
        
        // 自动语义推断
        TriggerRule(
            id: "rule_semantic_inference",
            name: "自动语义推断",
            description: "对象创建后自动推断语义类型",
            eventType: .objectCreated,
            condition: TriggerCondition(
                op: .eq,
                field: "status",
                value: AnyCodable("draft")
            ),
            action: TriggerAction(
                type: .startXingji,
                params: ["xingji_id": AnyCodable("xingji.semantic_inference")]
            ),
            priority: .high
        ),
        
        // 自动关系发现
        TriggerRule(
            id: "rule_relation_discovery",
            name: "自动关系发现",
            description: "属性就绪后自动发现对象间关系",
            eventType: .objectPropertiesReady,
            action: TriggerAction(
                type: .startXingji,
                params: ["xingji_id": AnyCodable("xingji.relation_discovery")]
            ),
            priority: .medium,
            delayMs: 1000,
            batchWindowMs: 2000
        ),
        
        // 对象就绪通知
        TriggerRule(
            id: "rule_object_ready_notify",
            name: "对象就绪通知",
            description: "对象准备好后通知用户",
            eventType: .objectReady,
            action: TriggerAction(
                type: .notify,
                params: ["template": AnyCodable("import_complete")]
            ),
            priority: .low
        )
    ]
}
