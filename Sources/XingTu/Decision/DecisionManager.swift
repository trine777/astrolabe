// DecisionManager.swift
// 星图 - 决策管理器
// 版本: v0.2.0

import Foundation
import SQLite

/// 决策管理器 - 处理 AI 决策的应用和审核
public actor DecisionManager {
    
    // MARK: - 单例
    
    public static let shared = DecisionManager()
    
    // MARK: - 属性

    private var decisions: [UUID: AIDecision] = [:]
    private let metaStore: MetaStore
    private let reviewQueue: ReviewQueue
    private let sqliteManager: SQLiteManager
    private let eventBus: EventBus

    // MARK: - 初始化

    public init(
        metaStore: MetaStore = MetaStore(),
        reviewQueue: ReviewQueue = ReviewQueue(),
        sqliteManager: SQLiteManager = .shared,
        eventBus: EventBus = .shared
    ) {
        self.metaStore = metaStore
        self.reviewQueue = reviewQueue
        self.sqliteManager = sqliteManager
        self.eventBus = eventBus
    }
    
    // MARK: - 决策处理
    
    /// 处理决策
    public func processDecision(
        _ decision: AIDecision,
        autoApplyThreshold: Double = 0.85,
        reviewThreshold: Double = 0.50
    ) async -> DecisionProcessResult {
        var mutableDecision = decision
        var applied = false
        var queued = false
        
        // 记录决策（内存 + SQLite）
        decisions[decision.id] = decision
        persistDecision(decision)

        if decision.confidence >= autoApplyThreshold {
            // 高置信度：自动应用
            do {
                try await applyDecision(decision)
                mutableDecision.status = .applied
                mutableDecision.wasAutoApplied = true
                mutableDecision.appliedAt = Date()
                applied = true
                print("✅ [DecisionManager] 自动应用: \(decision.actionType.rawValue) (置信度: \(String(format: "%.0f%%", decision.confidence * 100)))")
            } catch {
                print("⚠️ [DecisionManager] 应用失败: \(error)")
                return DecisionProcessResult(applied: false, queued: false, error: error.localizedDescription)
            }
        } else if decision.confidence >= reviewThreshold {
            // 中置信度：应用但加入审核队列
            do {
                try await applyDecision(decision)
                mutableDecision.status = .applied
                mutableDecision.wasAutoApplied = true
                mutableDecision.appliedAt = Date()
                applied = true
                
                // 加入审核队列
                await reviewQueue.add(decision: decision)
                queued = true
                print("📋 [DecisionManager] 应用并排队审核: \(decision.actionType.rawValue) (置信度: \(String(format: "%.0f%%", decision.confidence * 100)))")
            } catch {
                print("⚠️ [DecisionManager] 应用失败: \(error)")
                return DecisionProcessResult(applied: false, queued: false, error: error.localizedDescription)
            }
        } else {
            // 低置信度：仅加入审核队列
            await reviewQueue.add(decision: decision)
            queued = true
            print("📋 [DecisionManager] 排队审核: \(decision.actionType.rawValue) (置信度: \(String(format: "%.0f%%", decision.confidence * 100)))")
        }
        
        decisions[decision.id] = mutableDecision
        updateDecisionInDB(mutableDecision)
        return DecisionProcessResult(applied: applied, queued: queued)
    }
    
    // MARK: - 应用决策
    
    /// 应用决策到元数据
    private func applyDecision(_ decision: AIDecision) async throws {
        guard let propertyId = decision.propertyId else {
            throw DecisionError.missingPropertyId
        }
        
        guard var property = try await metaStore.getProperty(propertyId) else {
            throw DecisionError.propertyNotFound(propertyId)
        }
        
        // 根据动作类型应用更改
        switch decision.actionType {
        case .rename:
            if case .string(let name) = decision.proposedValue {
                property = MetaProperty(
                    id: property.id,
                    objectId: property.objectId,
                    originalName: property.originalName,
                    dataType: property.dataType,
                    sampleValues: property.sampleValues,
                    nullCount: property.nullCount,
                    uniqueCount: property.uniqueCount,
                    displayName: name,
                    description: property.description,
                    semanticType: property.semanticType,
                    unit: property.unit,
                    format: property.format,
                    businessRules: property.businessRules,
                    visualPreference: property.visualPreference,
                    userConfirmedAt: property.userConfirmedAt,
                    aiInferred: property.aiInferred
                )
            }
            
        case .setSemanticType:
            if case .semanticType(let type) = decision.proposedValue {
                property = MetaProperty(
                    id: property.id,
                    objectId: property.objectId,
                    originalName: property.originalName,
                    dataType: property.dataType,
                    sampleValues: property.sampleValues,
                    nullCount: property.nullCount,
                    uniqueCount: property.uniqueCount,
                    displayName: property.displayName,
                    description: property.description,
                    semanticType: type,
                    unit: property.unit,
                    format: property.format,
                    businessRules: property.businessRules,
                    visualPreference: property.visualPreference,
                    userConfirmedAt: property.userConfirmedAt,
                    aiInferred: MetaProperty.AIInferredInfo(
                        inferredSemanticType: type,
                        confidence: decision.confidence,
                        reasoning: decision.reasoning,
                        inferredAt: Date()
                    )
                )
            }
            
        case .setDescription:
            if case .string(let desc) = decision.proposedValue {
                property = MetaProperty(
                    id: property.id,
                    objectId: property.objectId,
                    originalName: property.originalName,
                    dataType: property.dataType,
                    sampleValues: property.sampleValues,
                    nullCount: property.nullCount,
                    uniqueCount: property.uniqueCount,
                    displayName: property.displayName,
                    description: desc,
                    semanticType: property.semanticType,
                    unit: property.unit,
                    format: property.format,
                    businessRules: property.businessRules,
                    visualPreference: property.visualPreference,
                    userConfirmedAt: property.userConfirmedAt,
                    aiInferred: property.aiInferred
                )
            }
            
        case .setUnit:
            if case .string(let unit) = decision.proposedValue {
                property = MetaProperty(
                    id: property.id,
                    objectId: property.objectId,
                    originalName: property.originalName,
                    dataType: property.dataType,
                    sampleValues: property.sampleValues,
                    nullCount: property.nullCount,
                    uniqueCount: property.uniqueCount,
                    displayName: property.displayName,
                    description: property.description,
                    semanticType: property.semanticType,
                    unit: unit,
                    format: property.format,
                    businessRules: property.businessRules,
                    visualPreference: property.visualPreference,
                    userConfirmedAt: property.userConfirmedAt,
                    aiInferred: property.aiInferred
                )
            }
            
        default:
            throw DecisionError.unsupportedAction(decision.actionType)
        }
        
        // 保存更新
        let _ = try await metaStore.updateProperty(property)

        // 发射审计事件
        await eventBus.emitAIDecisionMade(
            correlationId: nil,
            decisionId: decision.id,
            agentType: decision.agentType,
            objectId: decision.objectId,
            propertyId: decision.propertyId,
            actionType: decision.actionType.rawValue,
            proposedValue: decision.proposedValueString,
            confidence: decision.confidence,
            reasoning: decision.reasoning
        )
    }
    
    // MARK: - 回滚决策
    
    /// 回滚决策
    public func rollbackDecision(_ decisionId: UUID) async throws {
        guard var decision = decisions[decisionId] else {
            throw DecisionError.decisionNotFound(decisionId)
        }
        
        guard let previousValue = decision.previousValue else {
            throw DecisionError.noPreviousValue
        }
        
        // 创建回滚决策
        var rollbackDecision = decision
        rollbackDecision.proposedValue = previousValue
        
        try await applyDecision(rollbackDecision)
        
        decision.status = .rolledBack
        decisions[decisionId] = decision
        
        print("↩️ [DecisionManager] 已回滚: \(decision.actionType.rawValue)")
    }
    
    // MARK: - 查询
    
    /// 获取决策
    public func getDecision(_ id: UUID) -> AIDecision? {
        return decisions[id]
    }
    
    /// 获取对象的所有决策
    public func getDecisions(objectId: UUID) -> [AIDecision] {
        return decisions.values.filter { $0.objectId == objectId }
    }
    
    /// 获取待审核的决策
    public func getPendingDecisions() -> [AIDecision] {
        return decisions.values.filter { $0.status == .pending }
    }

    // MARK: - SQLite 持久化

    /// 将决策写入 ai_decisions 表
    private func persistDecision(_ decision: AIDecision) {
        do {
            let db = try sqliteManager.getConnection()
            let encoder = JSONEncoder()
            let proposedData = try encoder.encode(decision.proposedValue)
            let proposedStr = String(data: proposedData, encoding: .utf8) ?? ""
            var previousStr: String?
            if let prev = decision.previousValue {
                let prevData = try encoder.encode(prev)
                previousStr = String(data: prevData, encoding: .utf8)
            }

            let insert = SQLiteManager.aiDecisions.insert(
                SQLiteManager.decId <- decision.id.uuidString,
                SQLiteManager.decAgentType <- decision.agentType,
                SQLiteManager.decObjectId <- decision.objectId.uuidString,
                SQLiteManager.decPropertyId <- decision.propertyId?.uuidString,
                SQLiteManager.decRelationId <- decision.relationId?.uuidString,
                SQLiteManager.decActionType <- decision.actionType.rawValue,
                SQLiteManager.decProposedValue <- proposedStr,
                SQLiteManager.decPreviousValue <- previousStr,
                SQLiteManager.decConfidence <- decision.confidence,
                SQLiteManager.decReasoning <- decision.reasoning,
                SQLiteManager.decStatus <- decision.status.rawValue,
                SQLiteManager.decWasAutoApplied <- decision.wasAutoApplied,
                SQLiteManager.decCreatedAt <- decision.createdAt,
                SQLiteManager.decAppliedAt <- decision.appliedAt
            )
            try db.run(insert)
        } catch {
            print("⚠️ [DecisionManager] 决策持久化失败: \(error)")
        }
    }

    /// 更新已有决策的状态
    private func updateDecisionInDB(_ decision: AIDecision) {
        do {
            let db = try sqliteManager.getConnection()
            let target = SQLiteManager.aiDecisions.filter(
                SQLiteManager.decId == decision.id.uuidString
            )
            try db.run(target.update(
                SQLiteManager.decStatus <- decision.status.rawValue,
                SQLiteManager.decWasAutoApplied <- decision.wasAutoApplied,
                SQLiteManager.decAppliedAt <- decision.appliedAt
            ))
        } catch {
            print("⚠️ [DecisionManager] 决策状态更新失败: \(error)")
        }
    }
}

// MARK: - 错误类型

public enum DecisionError: Error, LocalizedError {
    case missingPropertyId
    case propertyNotFound(UUID)
    case decisionNotFound(UUID)
    case unsupportedAction(ActionType)
    case noPreviousValue
    case applyFailed(String)
    
    public var errorDescription: String? {
        switch self {
        case .missingPropertyId:
            return "决策缺少属性 ID"
        case .propertyNotFound(let id):
            return "属性不存在: \(id)"
        case .decisionNotFound(let id):
            return "决策不存在: \(id)"
        case .unsupportedAction(let action):
            return "不支持的动作类型: \(action.rawValue)"
        case .noPreviousValue:
            return "没有之前的值可回滚"
        case .applyFailed(let msg):
            return "应用失败: \(msg)"
        }
    }
}
