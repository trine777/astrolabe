// ReviewQueue.swift
// 星图 - 审核队列
// 版本: v0.2.0

import Foundation
import Combine
import SQLite

// MARK: - 审核项

/// 审核项
public struct ReviewItem: Identifiable, Codable, Sendable {
    public let id: UUID
    public let decisionId: UUID
    
    // 快照
    public let objectId: UUID
    public let objectName: String
    public let propertyId: UUID?
    public let propertyName: String?
    
    // 决策摘要
    public let agentType: String
    public let actionType: ActionType
    public let proposedValue: DecisionValue
    public let currentValue: DecisionValue?
    public let confidence: Double
    public let reasoning: String
    
    // 上下文
    public let sampleValues: [String]?
    public let relatedContext: String?
    
    // 状态
    public var status: ReviewStatus
    public let priority: Int
    
    // 审核
    public var reviewedBy: String?
    public var reviewedAt: Date?
    public var reviewComment: String?
    public var modifiedValue: DecisionValue?
    
    // 时间
    public let createdAt: Date
    public let expiresAt: Date?
    
    public init(
        id: UUID = UUID(),
        decision: AIDecision,
        objectName: String,
        propertyName: String?,
        sampleValues: [String]? = nil,
        expiresAt: Date? = nil
    ) {
        self.id = id
        self.decisionId = decision.id
        self.objectId = decision.objectId
        self.objectName = objectName
        self.propertyId = decision.propertyId
        self.propertyName = propertyName
        self.agentType = decision.agentType
        self.actionType = decision.actionType
        self.proposedValue = decision.proposedValue
        self.currentValue = decision.previousValue
        self.confidence = decision.confidence
        self.reasoning = decision.reasoning
        self.sampleValues = sampleValues
        self.relatedContext = nil
        self.status = .pending
        self.priority = Int((1 - decision.confidence) * 100)  // 置信度越低优先级越高
        self.createdAt = Date()
        self.expiresAt = expiresAt
    }
}

// MARK: - 审核状态

public enum ReviewStatus: String, Codable, Sendable {
    case pending = "pending"
    case approved = "approved"
    case rejected = "rejected"
    case modified = "modified"
    case expired = "expired"
}

// MARK: - 审核队列

/// 审核队列 - 管理待审核的 AI 决策
public actor ReviewQueue {
    
    // MARK: - 单例
    
    public static let shared = ReviewQueue()
    
    // MARK: - 属性

    private var items: [UUID: ReviewItem] = [:]
    private let metaStore: MetaStore
    private let sqliteManager: SQLiteManager

    // Combine 发布者
    private let itemsSubject = CurrentValueSubject<[ReviewItem], Never>([])

    // 默认过期时间（72小时）
    private let defaultExpirationHours: Int = 72

    // MARK: - 初始化

    public init(
        metaStore: MetaStore = MetaStore(),
        sqliteManager: SQLiteManager = .shared
    ) {
        self.metaStore = metaStore
        self.sqliteManager = sqliteManager
    }
    
    // MARK: - 添加审核项
    
    /// 添加决策到审核队列
    public func add(decision: AIDecision) async {
        // 获取对象名称
        let objectName: String
        if let object = try? await metaStore.getObject(id: decision.objectId) {
            objectName = object.name
        } else {
            objectName = "未知对象"
        }
        
        // 获取属性名称和样本值
        var propertyName: String?
        var sampleValues: [String]?
        if let propertyId = decision.propertyId,
           let property = try? await metaStore.getProperty(propertyId) {
            propertyName = property.displayName ?? property.originalName
            sampleValues = property.sampleValues
        }
        
        // 计算过期时间
        let expiresAt = Calendar.current.date(byAdding: .hour, value: defaultExpirationHours, to: Date())
        
        // 创建审核项
        let item = ReviewItem(
            decision: decision,
            objectName: objectName,
            propertyName: propertyName,
            sampleValues: sampleValues,
            expiresAt: expiresAt
        )
        
        items[item.id] = item
        persistItem(item)
        publishItems()

        print("📋 [ReviewQueue] 添加审核项: \(item.actionType.rawValue) - \(objectName).\(propertyName ?? "?")")
    }
    
    // MARK: - 审核操作
    
    /// 批准决策
    public func approve(_ itemId: UUID, by userId: String? = nil, comment: String? = nil) async throws {
        guard var item = items[itemId] else {
            throw ReviewError.itemNotFound(itemId)
        }
        
        item.status = .approved
        item.reviewedBy = userId
        item.reviewedAt = Date()
        item.reviewComment = comment

        items[itemId] = item
        updateItemInDB(item)
        publishItems()

        print("✅ [ReviewQueue] 已批准: \(item.actionType.rawValue)")
    }
    
    /// 拒绝决策
    public func reject(_ itemId: UUID, by userId: String? = nil, comment: String? = nil) async throws {
        guard var item = items[itemId] else {
            throw ReviewError.itemNotFound(itemId)
        }
        
        item.status = .rejected
        item.reviewedBy = userId
        item.reviewedAt = Date()
        item.reviewComment = comment

        items[itemId] = item
        updateItemInDB(item)
        publishItems()

        // 如果决策已应用，需要回滚
        // TODO: 调用 DecisionManager.rollbackDecision

        print("❌ [ReviewQueue] 已拒绝: \(item.actionType.rawValue)")
    }
    
    /// 修改后批准
    public func approveWithModification(
        _ itemId: UUID,
        modifiedValue: DecisionValue,
        by userId: String? = nil,
        comment: String? = nil
    ) async throws {
        guard var item = items[itemId] else {
            throw ReviewError.itemNotFound(itemId)
        }
        
        item.status = .modified
        item.modifiedValue = modifiedValue
        item.reviewedBy = userId
        item.reviewedAt = Date()
        item.reviewComment = comment

        items[itemId] = item
        updateItemInDB(item)
        publishItems()

        // TODO: 应用修改后的值

        print("✏️ [ReviewQueue] 已修改: \(item.actionType.rawValue)")
    }
    
    /// 批量批准
    public func batchApprove(_ itemIds: [UUID], by userId: String? = nil) async throws {
        for itemId in itemIds {
            try await approve(itemId, by: userId)
        }
    }
    
    /// 批量拒绝
    public func batchReject(_ itemIds: [UUID], by userId: String? = nil) async throws {
        for itemId in itemIds {
            try await reject(itemId, by: userId)
        }
    }
    
    // MARK: - 过期处理
    
    /// 清理过期项
    public func cleanExpired() {
        let now = Date()
        var expiredCount = 0
        
        for (id, item) in items {
            if let expiresAt = item.expiresAt, expiresAt < now, item.status == .pending {
                var mutableItem = item
                mutableItem.status = .expired
                items[id] = mutableItem
                expiredCount += 1
            }
        }
        
        if expiredCount > 0 {
            publishItems()
            print("⏰ [ReviewQueue] \(expiredCount) 项已过期")
        }
    }
    
    // MARK: - 查询
    
    /// 获取所有待审核项
    public func getPendingItems() -> [ReviewItem] {
        return items.values
            .filter { $0.status == .pending }
            .sorted { $0.priority > $1.priority }
    }
    
    /// 获取特定对象的待审核项
    public func getPendingItems(objectId: UUID) -> [ReviewItem] {
        return items.values
            .filter { $0.objectId == objectId && $0.status == .pending }
            .sorted { $0.priority > $1.priority }
    }
    
    /// 获取审核项
    public func getItem(_ id: UUID) -> ReviewItem? {
        return items[id]
    }
    
    /// 获取待审核数量
    public func pendingCount() -> Int {
        return items.values.filter { $0.status == .pending }.count
    }
    
    /// 获取所有项目
    public func getAllItems() -> [ReviewItem] {
        return Array(items.values).sorted { $0.createdAt > $1.createdAt }
    }
    
    // MARK: - SQLite 持久化

    /// 将审核项写入 review_queue 表
    private func persistItem(_ item: ReviewItem) {
        do {
            let db = try sqliteManager.getConnection()
            let encoder = JSONEncoder()
            let proposedData = try encoder.encode(item.proposedValue)
            let proposedStr = String(data: proposedData, encoding: .utf8) ?? ""
            var currentStr: String?
            if let cur = item.currentValue {
                let curData = try encoder.encode(cur)
                currentStr = String(data: curData, encoding: .utf8)
            }

            let insert = SQLiteManager.reviewQueue.insert(
                SQLiteManager.revId <- item.id.uuidString,
                SQLiteManager.revDecisionId <- item.decisionId.uuidString,
                SQLiteManager.revObjectId <- item.objectId.uuidString,
                SQLiteManager.revObjectName <- item.objectName,
                SQLiteManager.revPropertyId <- item.propertyId?.uuidString,
                SQLiteManager.revPropertyName <- item.propertyName,
                SQLiteManager.revAgentType <- item.agentType,
                SQLiteManager.revActionType <- item.actionType.rawValue,
                SQLiteManager.revProposedValue <- proposedStr,
                SQLiteManager.revCurrentValue <- currentStr,
                SQLiteManager.revConfidence <- item.confidence,
                SQLiteManager.revReasoning <- item.reasoning,
                SQLiteManager.revSampleValues <- SQLiteManager.encodeJSON(item.sampleValues),
                SQLiteManager.revStatus <- item.status.rawValue,
                SQLiteManager.revPriority <- item.priority,
                SQLiteManager.revCreatedAt <- item.createdAt,
                SQLiteManager.revExpiresAt <- item.expiresAt
            )
            try db.run(insert)
        } catch {
            print("⚠️ [ReviewQueue] 审核项持久化失败: \(error)")
        }
    }

    /// 更新审核项状态
    private func updateItemInDB(_ item: ReviewItem) {
        do {
            let db = try sqliteManager.getConnection()
            let target = SQLiteManager.reviewQueue.filter(
                SQLiteManager.revId == item.id.uuidString
            )
            var modifiedStr: String?
            if let mod = item.modifiedValue {
                let encoder = JSONEncoder()
                let modData = try encoder.encode(mod)
                modifiedStr = String(data: modData, encoding: .utf8)
            }
            try db.run(target.update(
                SQLiteManager.revStatus <- item.status.rawValue,
                SQLiteManager.revReviewedBy <- item.reviewedBy,
                SQLiteManager.revReviewedAt <- item.reviewedAt,
                SQLiteManager.revReviewComment <- item.reviewComment,
                SQLiteManager.revModifiedValue <- modifiedStr
            ))
        } catch {
            print("⚠️ [ReviewQueue] 审核项状态更新失败: \(error)")
        }
    }

    // MARK: - Combine 发布

    private func publishItems() {
        itemsSubject.send(Array(items.values))
    }

    /// 获取 Publisher
    public nonisolated func itemsPublisher() -> AnyPublisher<[ReviewItem], Never> {
        return itemsSubject.eraseToAnyPublisher()
    }
}

// MARK: - 错误类型

public enum ReviewError: Error, LocalizedError {
    case itemNotFound(UUID)
    case alreadyReviewed(UUID)
    case expired(UUID)
    
    public var errorDescription: String? {
        switch self {
        case .itemNotFound(let id):
            return "审核项不存在: \(id)"
        case .alreadyReviewed(let id):
            return "审核项已处理: \(id)"
        case .expired(let id):
            return "审核项已过期: \(id)"
        }
    }
}
