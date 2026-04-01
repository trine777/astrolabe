// SemanticInferenceXingJi.swift
// 星图 - 语义推断行技
// 版本: v0.2.0

import Foundation

/// 语义推断行技 - 对象创建后自动推断语义类型
public class SemanticInferenceXingJi: XingJiProtocol {
    
    public let id = "xingji.semantic_inference"
    public let version = "0.2.0"
    public let name = "语义推断行技"
    
    private let aiService: AIServiceProtocol?
    private let metaStore: MetaStore
    private let eventBus: EventBus
    private let decisionManager: DecisionManager
    
    // 置信度阈值
    private let autoApplyThreshold: Double
    private let reviewThreshold: Double
    
    public init(
        aiService: AIServiceProtocol? = nil,
        metaStore: MetaStore = MetaStore(),
        eventBus: EventBus = .shared,
        decisionManager: DecisionManager = DecisionManager(),
        autoApplyThreshold: Double = 0.85,
        reviewThreshold: Double = 0.50
    ) {
        self.aiService = aiService
        self.metaStore = metaStore
        self.eventBus = eventBus
        self.decisionManager = decisionManager
        self.autoApplyThreshold = autoApplyThreshold
        self.reviewThreshold = reviewThreshold
    }
    
    public func execute(context: XingJiContext) async throws -> XingJiResult {
        // 1. 从事件中获取对象信息
        guard let objectEvent = context.triggerEvent as? ObjectCreatedEvent else {
            return .failure("无效的触发事件，需要 ObjectCreatedEvent")
        }
        
        let objectId = objectEvent.objectId
        
        print("🔮 [SemanticInference] 开始推断: \(objectEvent.objectName)")
        
        // 2. 获取对象和属性
        guard let object = try await metaStore.getObject(id: objectId) else {
            return .failure("对象不存在: \(objectId)")
        }
        
        let properties = try await metaStore.getProperties(objectId: objectId)
        
        guard !properties.isEmpty else {
            return .failure("对象没有属性")
        }
        
        // 3. 调用 AI 推断
        var decisions: [AIDecision] = []
        
        if let service = aiService {
            // 使用 AI 服务
            decisions = try await inferWithAI(
                service: service,
                object: object,
                properties: properties,
                correlationId: context.correlationId
            )
        } else {
            // 使用规则推断（备用）
            decisions = inferWithRules(
                object: object,
                properties: properties,
                correlationId: context.correlationId
            )
        }
        
        // 4. 处理决策
        var autoAppliedCount = 0
        var queuedCount = 0
        
        for decision in decisions {
            let result = await decisionManager.processDecision(
                decision,
                autoApplyThreshold: autoApplyThreshold,
                reviewThreshold: reviewThreshold
            )
            
            if result.applied {
                autoAppliedCount += 1
            }
            if result.queued {
                queuedCount += 1
            }
            
            // 发布决策事件
            await eventBus.emitAIDecisionMade(
                correlationId: context.correlationId,
                decisionId: decision.id,
                agentType: "semantic_inference",
                objectId: objectId,
                propertyId: decision.propertyId,
                actionType: decision.actionType.rawValue,
                proposedValue: decision.proposedValueString,
                confidence: decision.confidence,
                reasoning: decision.reasoning
            )
        }
        
        // 5. 发布属性就绪事件
        await eventBus.emitObjectPropertiesReady(
            correlationId: context.correlationId,
            objectId: objectId,
            propertyCount: properties.count,
            autoAppliedCount: autoAppliedCount,
            pendingReviewCount: queuedCount
        )
        
        print("✅ [SemanticInference] 推断完成: \(decisions.count) 决策, \(autoAppliedCount) 自动应用, \(queuedCount) 待审核")
        
        return XingJiResult(
            success: true,
            output: [
                "object_id": objectId.uuidString,
                "total_decisions": decisions.count
            ],
            decisionsCount: decisions.count,
            appliedCount: autoAppliedCount,
            queuedCount: queuedCount
        )
    }
    
    // MARK: - AI 推断
    
    private func inferWithAI(
        service: AIServiceProtocol,
        object: MetaObject,
        properties: [MetaProperty],
        correlationId: UUID
    ) async throws -> [AIDecision] {
        // 准备属性信息
        let propertyInfos = properties.map { PropertyInfo(from: $0) }
        
        // 调用 AI 推断语义类型
        let inferences = try await service.inferSemanticTypes(
            properties: propertyInfos,
            objectName: object.name
        )
        
        // 转换为决策
        var decisions: [AIDecision] = []
        
        for inference in inferences {
            guard let property = properties.first(where: { $0.originalName == inference.originalName }) else {
                continue
            }
            
            // 语义类型决策
            if let semanticType = MetaProperty.SemanticType(rawValue: inference.semanticType) {
                var previousType: DecisionValue? = nil
                if let existingType = property.semanticType {
                    previousType = DecisionValue.semanticType(existingType)
                }
                let decision = AIDecision(
                    agentType: "semantic_inference",
                    objectId: object.id,
                    propertyId: property.id,
                    actionType: .setSemanticType,
                    proposedValue: .semanticType(semanticType),
                    previousValue: previousType,
                    confidence: inference.confidence,
                    reasoning: inference.reasoning
                )
                decisions.append(decision)
            }
            
            // 显示名称决策
            if let displayName = inference.displayName, !displayName.isEmpty {
                let previousDisplayName: DecisionValue? = property.displayName.isEmpty ? nil : DecisionValue.string(property.displayName)
                let decision = AIDecision(
                    agentType: "semantic_inference",
                    objectId: object.id,
                    propertyId: property.id,
                    actionType: .rename,
                    proposedValue: .string(displayName),
                    previousValue: previousDisplayName,
                    confidence: inference.confidence,
                    reasoning: "基于列名和数据样本推断的业务名称"
                )
                decisions.append(decision)
            }
            
            // 描述决策
            if let description = inference.description, !description.isEmpty {
                var previousDescription: DecisionValue? = nil
                if let existingDesc = property.description {
                    previousDescription = DecisionValue.string(existingDesc)
                }
                let decision = AIDecision(
                    agentType: "semantic_inference",
                    objectId: object.id,
                    propertyId: property.id,
                    actionType: .setDescription,
                    proposedValue: .string(description),
                    previousValue: previousDescription,
                    confidence: inference.confidence * 0.9,  // 描述置信度略低
                    reasoning: "AI 生成的字段描述"
                )
                decisions.append(decision)
            }
        }
        
        return decisions
    }
    
    // MARK: - 规则推断（备用）
    
    private func inferWithRules(
        object: MetaObject,
        properties: [MetaProperty],
        correlationId: UUID
    ) -> [AIDecision] {
        var decisions: [AIDecision] = []
        
        for property in properties {
            let name = property.originalName.lowercased()
            var inferredType: MetaProperty.SemanticType?
            var confidence: Double = 0.6
            var reasoning = ""
            
            // 基于列名的规则推断
            if name.contains("id") && (name.hasSuffix("id") || name.hasSuffix("_id")) {
                if name == "id" {
                    inferredType = .primaryKey
                    confidence = 0.9
                    reasoning = "列名为 'id'，推断为主键"
                } else {
                    inferredType = .foreignKey
                    confidence = 0.8
                    reasoning = "列名包含 '_id' 后缀，推断为外键"
                }
            } else if name.contains("email") {
                inferredType = .email
                confidence = 0.9
                reasoning = "列名包含 'email'"
            } else if name.contains("phone") || name.contains("tel") || name.contains("mobile") {
                inferredType = .phone
                confidence = 0.85
                reasoning = "列名包含电话相关关键词"
            } else if name.contains("name") && (name.contains("user") || name.contains("person")) {
                inferredType = .personName
                confidence = 0.75
                reasoning = "列名包含人名相关关键词"
            } else if name.contains("amount") || name.contains("price") || name.contains("cost") || name.contains("金额") {
                inferredType = .amount
                confidence = 0.85
                reasoning = "列名包含金额相关关键词"
            } else if name.contains("date") || name.contains("time") || name.contains("_at") {
                if property.dataType == .datetime || property.dataType == .date {
                    inferredType = .timestamp
                    confidence = 0.9
                    reasoning = "列名和数据类型都表明是时间戳"
                }
            } else if name.contains("status") || name.contains("state") || name.contains("状态") {
                inferredType = .status
                confidence = 0.8
                reasoning = "列名包含状态相关关键词"
            } else if name.contains("type") || name.contains("category") || name.contains("类型") || name.contains("分类") {
                inferredType = .category
                confidence = 0.75
                reasoning = "列名包含分类相关关键词"
            } else if property.uniqueCount < 20 && property.uniqueCount > 1 {
                inferredType = .category
                confidence = 0.6
                reasoning = "唯一值数量少，可能是分类字段"
            }
            
            if let type = inferredType {
                let decision = AIDecision(
                    agentType: "semantic_inference_rules",
                    objectId: object.id,
                    propertyId: property.id,
                    actionType: .setSemanticType,
                    proposedValue: .semanticType(type),
                    previousValue: property.semanticType.map { .semanticType($0) },
                    confidence: confidence,
                    reasoning: reasoning
                )
                decisions.append(decision)
            }
        }
        
        return decisions
    }
}
