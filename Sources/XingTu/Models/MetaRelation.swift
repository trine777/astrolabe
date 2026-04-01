// 星图 (XingTu) - 元数据关系模型
// 归属: 星空座 (Xingkongzuo)

import Foundation

/// 星空座：对象之间的关系（外键、关联）
public struct MetaRelation: Identifiable, Codable, Equatable {
    public let id: UUID
    
    // MARK: - 源端
    
    public var sourceObjectId: UUID            // 源对象
    public var sourcePropertyId: UUID          // 源属性
    
    // MARK: - 目标端
    
    public var targetObjectId: UUID            // 目标对象
    public var targetPropertyId: UUID          // 目标属性
    
    // MARK: - 关系信息
    
    public var relationType: RelationType      // 关系类型
    public var relationName: String?           // 关系名称（如："属于"、"包含"）
    public var description: String?            // 关系说明
    
    // MARK: - 确认状态
    
    public var isAIInferred: Bool              // 是否 AI 推断
    public var confidence: Double?             // AI 置信度
    public var isConfirmed: Bool               // 用户是否确认
    public var confirmedAt: Date?
    
    // MARK: - 关系类型
    
    public enum RelationType: String, Codable, CaseIterable {
        case oneToOne = "oneToOne"         // 1:1
        case oneToMany = "oneToMany"       // 1:N
        case manyToOne = "manyToOne"       // N:1
        case manyToMany = "manyToMany"     // M:N
        
        public var displayName: String {
            switch self {
            case .oneToOne: return "一对一"
            case .oneToMany: return "一对多"
            case .manyToOne: return "多对一"
            case .manyToMany: return "多对多"
            }
        }
        
        public var symbol: String {
            switch self {
            case .oneToOne: return "1:1"
            case .oneToMany: return "1:N"
            case .manyToOne: return "N:1"
            case .manyToMany: return "M:N"
            }
        }
        
        /// 反向关系类型
        public var inverse: RelationType {
            switch self {
            case .oneToOne: return .oneToOne
            case .oneToMany: return .manyToOne
            case .manyToOne: return .oneToMany
            case .manyToMany: return .manyToMany
            }
        }
    }
    
    // MARK: - 初始化
    
    public init(
        id: UUID = UUID(),
        sourceObjectId: UUID,
        sourcePropertyId: UUID,
        targetObjectId: UUID,
        targetPropertyId: UUID,
        relationType: RelationType,
        relationName: String? = nil,
        description: String? = nil,
        isAIInferred: Bool = false,
        confidence: Double? = nil,
        isConfirmed: Bool = false,
        confirmedAt: Date? = nil
    ) {
        self.id = id
        self.sourceObjectId = sourceObjectId
        self.sourcePropertyId = sourcePropertyId
        self.targetObjectId = targetObjectId
        self.targetPropertyId = targetPropertyId
        self.relationType = relationType
        self.relationName = relationName
        self.description = description
        self.isAIInferred = isAIInferred
        self.confidence = confidence
        self.isConfirmed = isConfirmed
        self.confirmedAt = confirmedAt
    }
    
    // MARK: - 便捷方法
    
    /// 确认关系
    public mutating func confirm() {
        self.isConfirmed = true
        self.confirmedAt = Date()
    }
    
    /// 创建反向关系
    public func createInverse() -> MetaRelation {
        MetaRelation(
            sourceObjectId: targetObjectId,
            sourcePropertyId: targetPropertyId,
            targetObjectId: sourceObjectId,
            targetPropertyId: sourcePropertyId,
            relationType: relationType.inverse,
            relationName: relationName.map { "反向: \($0)" },
            description: description,
            isAIInferred: isAIInferred,
            confidence: confidence,
            isConfirmed: isConfirmed,
            confirmedAt: confirmedAt
        )
    }
}

// MARK: - 摘要

extension MetaRelation {
    /// 生成关系摘要（用于 AI 上下文）
    public var summary: MetaRelationSummary {
        MetaRelationSummary(
            id: id,
            sourceObjectId: sourceObjectId,
            targetObjectId: targetObjectId,
            relationType: relationType.rawValue,
            relationName: relationName,
            isConfirmed: isConfirmed
        )
    }
}

/// 元数据关系摘要
public struct MetaRelationSummary: Codable {
    public let id: UUID
    public let sourceObjectId: UUID
    public let targetObjectId: UUID
    public let relationType: String
    public let relationName: String?
    public let isConfirmed: Bool
}
