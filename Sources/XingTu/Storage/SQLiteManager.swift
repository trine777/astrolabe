// 星图 (XingTu) - SQLite 管理器
// 存储层核心

import Foundation
import SQLite

/// SQLite 数据库管理器
public class SQLiteManager {
    
    // MARK: - 单例
    
    public static let shared = SQLiteManager()
    
    // MARK: - 属性
    
    private var db: Connection?
    private let dbPath: String
    
    // MARK: - 表定义
    
    // meta_objects 表
    static let metaObjects = Table("meta_objects")
    static let objId = Expression<String>("id")
    static let objName = Expression<String>("name")
    static let objOriginalName = Expression<String>("original_name")
    static let objType = Expression<String>("object_type")
    static let objDescription = Expression<String?>("description")
    static let objFilePath = Expression<String?>("file_path")
    static let objRowCount = Expression<Int?>("row_count")
    static let objStatus = Expression<String>("status")
    static let objTags = Expression<String?>("tags")  // JSON
    static let objCreatedAt = Expression<Date>("created_at")
    static let objUpdatedAt = Expression<Date>("updated_at")
    static let objConfirmedAt = Expression<Date?>("confirmed_at")
    static let objConfirmedBy = Expression<String?>("confirmed_by")
    
    // meta_properties 表
    static let metaProperties = Table("meta_properties")
    static let propId = Expression<String>("id")
    static let propObjectId = Expression<String>("object_id")
    static let propOriginalName = Expression<String>("original_name")
    static let propDataType = Expression<String>("data_type")
    static let propSampleValues = Expression<String?>("sample_values")  // JSON
    static let propNullCount = Expression<Int>("null_count")
    static let propUniqueCount = Expression<Int>("unique_count")
    static let propDisplayName = Expression<String?>("display_name")
    static let propDescription = Expression<String?>("description")
    static let propSemanticType = Expression<String?>("semantic_type")
    static let propUnit = Expression<String?>("unit")
    static let propFormat = Expression<String?>("format")
    static let propBusinessRules = Expression<String?>("business_rules")
    static let propVisualPreference = Expression<String?>("visual_preference")  // JSON
    static let propUserConfirmedAt = Expression<Date?>("user_confirmed_at")
    static let propAIInferred = Expression<String?>("ai_inferred")  // JSON
    
    // meta_relations 表
    static let metaRelations = Table("meta_relations")
    static let relId = Expression<String>("id")
    static let relSourceObjectId = Expression<String>("source_object_id")
    static let relSourcePropertyId = Expression<String>("source_property_id")
    static let relTargetObjectId = Expression<String>("target_object_id")
    static let relTargetPropertyId = Expression<String>("target_property_id")
    static let relType = Expression<String>("relation_type")
    static let relName = Expression<String?>("relation_name")
    static let relDescription = Expression<String?>("description")
    static let relIsAIInferred = Expression<Bool>("is_ai_inferred")
    static let relConfidence = Expression<Double?>("confidence")
    static let relIsConfirmed = Expression<Bool>("is_confirmed")
    static let relConfirmedAt = Expression<Date?>("confirmed_at")
    
    // meta_events 表（v1 兼容）
    static let metaEvents = Table("meta_events")
    static let evtId = Expression<String>("id")
    static let evtTimestamp = Expression<Date>("timestamp")
    static let evtType = Expression<String>("event_type")
    static let evtObjectId = Expression<String?>("object_id")
    static let evtPropertyId = Expression<String?>("property_id")
    static let evtActorType = Expression<String>("actor_type")
    static let evtActorId = Expression<String?>("actor_id")
    static let evtBeforeSnapshot = Expression<String?>("before_snapshot")
    static let evtAfterSnapshot = Expression<String?>("after_snapshot")
    static let evtDescription = Expression<String?>("description")

    // events 表（v2 事件总线持久化）
    static let events = Table("events")
    static let evtV2Id = Expression<String>("id")
    static let evtV2EventType = Expression<String>("event_type")
    static let evtV2Source = Expression<String>("source")
    static let evtV2CorrelationId = Expression<String?>("correlation_id")
    static let evtV2Payload = Expression<String>("payload")
    static let evtV2Timestamp = Expression<String>("timestamp")
    static let evtV2Processed = Expression<Int>("processed")
    static let evtV2ProcessedAt = Expression<String?>("processed_at")
    static let evtV2Processor = Expression<String?>("processor")

    // ai_decisions 表
    static let aiDecisions = Table("ai_decisions")
    static let decId = Expression<String>("id")
    static let decAgentType = Expression<String>("agent_type")
    static let decXingjiExecutionId = Expression<String?>("xingji_execution_id")
    static let decObjectId = Expression<String>("object_id")
    static let decPropertyId = Expression<String?>("property_id")
    static let decRelationId = Expression<String?>("relation_id")
    static let decActionType = Expression<String>("action_type")
    static let decProposedValue = Expression<String>("proposed_value")
    static let decPreviousValue = Expression<String?>("previous_value")
    static let decConfidence = Expression<Double>("confidence")
    static let decReasoning = Expression<String?>("reasoning")
    static let decStatus = Expression<String>("status")
    static let decWasAutoApplied = Expression<Bool>("was_auto_applied")
    static let decCreatedAt = Expression<Date>("created_at")
    static let decAppliedAt = Expression<Date?>("applied_at")
    static let decReviewId = Expression<String?>("review_id")
    static let decReviewedBy = Expression<String?>("reviewed_by")
    static let decReviewedAt = Expression<Date?>("reviewed_at")

    // review_queue 表
    static let reviewQueue = Table("review_queue")
    static let revId = Expression<String>("id")
    static let revDecisionId = Expression<String>("decision_id")
    static let revObjectId = Expression<String>("object_id")
    static let revObjectName = Expression<String>("object_name")
    static let revPropertyId = Expression<String?>("property_id")
    static let revPropertyName = Expression<String?>("property_name")
    static let revAgentType = Expression<String>("agent_type")
    static let revActionType = Expression<String>("action_type")
    static let revProposedValue = Expression<String>("proposed_value")
    static let revCurrentValue = Expression<String?>("current_value")
    static let revConfidence = Expression<Double>("confidence")
    static let revReasoning = Expression<String?>("reasoning")
    static let revSampleValues = Expression<String?>("sample_values")
    static let revStatus = Expression<String>("status")
    static let revPriority = Expression<Int>("priority")
    static let revReviewedBy = Expression<String?>("reviewed_by")
    static let revReviewedAt = Expression<Date?>("reviewed_at")
    static let revReviewComment = Expression<String?>("review_comment")
    static let revModifiedValue = Expression<String?>("modified_value")
    static let revCreatedAt = Expression<Date>("created_at")
    static let revExpiresAt = Expression<Date?>("expires_at")

    // xingji_executions 表
    static let xingjiExecutions = Table("xingji_executions")
    static let xeId = Expression<String>("id")
    static let xeXingjiId = Expression<String>("xingji_id")
    static let xeXingjiVersion = Expression<String?>("xingji_version")
    static let xeTriggerEventId = Expression<String?>("trigger_event_id")
    static let xeTriggerEventType = Expression<String?>("trigger_event_type")
    static let xeCorrelationId = Expression<String?>("correlation_id")
    static let xeInputParams = Expression<String?>("input_params")
    static let xeTargetObjectId = Expression<String?>("target_object_id")
    static let xeStatus = Expression<String>("status")
    static let xeCurrentCell = Expression<String?>("current_cell")
    static let xeProgress = Expression<Double>("progress")
    static let xeOutput = Expression<String?>("output")
    static let xeErrorMessage = Expression<String?>("error_message")
    static let xeCellsTotal = Expression<Int?>("cells_total")
    static let xeCellsCompleted = Expression<Int?>("cells_completed")
    static let xeDecisionsMade = Expression<Int?>("decisions_made")
    static let xeDecisionsApplied = Expression<Int?>("decisions_applied")
    static let xeReviewsQueued = Expression<Int?>("reviews_queued")
    static let xeCreatedAt = Expression<Date>("created_at")
    static let xeStartedAt = Expression<Date?>("started_at")
    static let xeCompletedAt = Expression<Date?>("completed_at")
    static let xeDurationMs = Expression<Int?>("duration_ms")

    // metric_defs 表
    static let metricDefs = Table("metric_defs")
    static let metId = Expression<String>("id")
    static let metName = Expression<String>("name")
    static let metDisplayName = Expression<String>("display_name")
    static let metDescription = Expression<String?>("description")
    static let metFormula = Expression<String>("formula")
    static let metSourceObjectIds = Expression<String?>("source_object_ids")  // JSON
    static let metUnit = Expression<String?>("unit")
    static let metAggregationType = Expression<String?>("aggregation_type")
    static let metDimensions = Expression<String?>("dimensions")  // JSON
    static let metTags = Expression<String?>("tags")  // JSON
    static let metStatus = Expression<String>("status")
    static let metCreatedAt = Expression<Date>("created_at")
    static let metUpdatedAt = Expression<Date>("updated_at")
    
    // MARK: - 初始化
    
    private init() {
        // 默认数据库路径
        let documentsPath = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        let appFolder = documentsPath.appendingPathComponent("XingTu", isDirectory: true)
        
        // 创建目录
        try? FileManager.default.createDirectory(at: appFolder, withIntermediateDirectories: true)
        
        self.dbPath = appFolder.appendingPathComponent("xingtu.db").path
    }
    
    /// 使用自定义路径初始化
    public init(path: String) {
        self.dbPath = path
    }
    
    // MARK: - 连接管理
    
    /// 打开数据库连接
    public func open() throws {
        db = try Connection(dbPath)
        try createTables()
    }
    
    /// 关闭数据库连接
    public func close() {
        db = nil
    }
    
    /// 获取数据库连接
    public func getConnection() throws -> Connection {
        if let db = db {
            return db
        }
        try open()
        guard let db = db else {
            throw SQLiteError.connectionFailed
        }
        return db
    }
    
    // MARK: - 表创建
    
    private func createTables() throws {
        guard let db = db else { return }
        
        // meta_objects
        try db.run(SQLiteManager.metaObjects.create(ifNotExists: true) { t in
            t.column(SQLiteManager.objId, primaryKey: true)
            t.column(SQLiteManager.objName)
            t.column(SQLiteManager.objOriginalName)
            t.column(SQLiteManager.objType)
            t.column(SQLiteManager.objDescription)
            t.column(SQLiteManager.objFilePath)
            t.column(SQLiteManager.objRowCount)
            t.column(SQLiteManager.objStatus, defaultValue: "draft")
            t.column(SQLiteManager.objTags)
            t.column(SQLiteManager.objCreatedAt)
            t.column(SQLiteManager.objUpdatedAt)
            t.column(SQLiteManager.objConfirmedAt)
            t.column(SQLiteManager.objConfirmedBy)
        })
        
        // meta_properties
        try db.run(SQLiteManager.metaProperties.create(ifNotExists: true) { t in
            t.column(SQLiteManager.propId, primaryKey: true)
            t.column(SQLiteManager.propObjectId)
            t.column(SQLiteManager.propOriginalName)
            t.column(SQLiteManager.propDataType)
            t.column(SQLiteManager.propSampleValues)
            t.column(SQLiteManager.propNullCount, defaultValue: 0)
            t.column(SQLiteManager.propUniqueCount, defaultValue: 0)
            t.column(SQLiteManager.propDisplayName)
            t.column(SQLiteManager.propDescription)
            t.column(SQLiteManager.propSemanticType)
            t.column(SQLiteManager.propUnit)
            t.column(SQLiteManager.propFormat)
            t.column(SQLiteManager.propBusinessRules)
            t.column(SQLiteManager.propVisualPreference)
            t.column(SQLiteManager.propUserConfirmedAt)
            t.column(SQLiteManager.propAIInferred)
            t.foreignKey(SQLiteManager.propObjectId, references: SQLiteManager.metaObjects, SQLiteManager.objId, delete: .cascade)
        })
        
        // meta_relations
        try db.run(SQLiteManager.metaRelations.create(ifNotExists: true) { t in
            t.column(SQLiteManager.relId, primaryKey: true)
            t.column(SQLiteManager.relSourceObjectId)
            t.column(SQLiteManager.relSourcePropertyId)
            t.column(SQLiteManager.relTargetObjectId)
            t.column(SQLiteManager.relTargetPropertyId)
            t.column(SQLiteManager.relType)
            t.column(SQLiteManager.relName)
            t.column(SQLiteManager.relDescription)
            t.column(SQLiteManager.relIsAIInferred, defaultValue: false)
            t.column(SQLiteManager.relConfidence)
            t.column(SQLiteManager.relIsConfirmed, defaultValue: false)
            t.column(SQLiteManager.relConfirmedAt)
        })
        
        // meta_events
        try db.run(SQLiteManager.metaEvents.create(ifNotExists: true) { t in
            t.column(SQLiteManager.evtId, primaryKey: true)
            t.column(SQLiteManager.evtTimestamp)
            t.column(SQLiteManager.evtType)
            t.column(SQLiteManager.evtObjectId)
            t.column(SQLiteManager.evtPropertyId)
            t.column(SQLiteManager.evtActorType)
            t.column(SQLiteManager.evtActorId)
            t.column(SQLiteManager.evtBeforeSnapshot)
            t.column(SQLiteManager.evtAfterSnapshot)
            t.column(SQLiteManager.evtDescription)
        })
        
        // metric_defs
        try db.run(SQLiteManager.metricDefs.create(ifNotExists: true) { t in
            t.column(SQLiteManager.metId, primaryKey: true)
            t.column(SQLiteManager.metName, unique: true)
            t.column(SQLiteManager.metDisplayName)
            t.column(SQLiteManager.metDescription)
            t.column(SQLiteManager.metFormula)
            t.column(SQLiteManager.metSourceObjectIds)
            t.column(SQLiteManager.metUnit)
            t.column(SQLiteManager.metAggregationType)
            t.column(SQLiteManager.metDimensions)
            t.column(SQLiteManager.metTags)
            t.column(SQLiteManager.metStatus, defaultValue: "draft")
            t.column(SQLiteManager.metCreatedAt)
            t.column(SQLiteManager.metUpdatedAt)
        })
        
        // v2: events 表（事件总线持久化）
        try db.run(SQLiteManager.events.create(ifNotExists: true) { t in
            t.column(SQLiteManager.evtV2Id, primaryKey: true)
            t.column(SQLiteManager.evtV2EventType)
            t.column(SQLiteManager.evtV2Source)
            t.column(SQLiteManager.evtV2CorrelationId)
            t.column(SQLiteManager.evtV2Payload)
            t.column(SQLiteManager.evtV2Timestamp)
            t.column(SQLiteManager.evtV2Processed, defaultValue: 0)
            t.column(SQLiteManager.evtV2ProcessedAt)
            t.column(SQLiteManager.evtV2Processor)
        })

        // v2: ai_decisions 表
        try db.run(SQLiteManager.aiDecisions.create(ifNotExists: true) { t in
            t.column(SQLiteManager.decId, primaryKey: true)
            t.column(SQLiteManager.decAgentType)
            t.column(SQLiteManager.decXingjiExecutionId)
            t.column(SQLiteManager.decObjectId)
            t.column(SQLiteManager.decPropertyId)
            t.column(SQLiteManager.decRelationId)
            t.column(SQLiteManager.decActionType)
            t.column(SQLiteManager.decProposedValue)
            t.column(SQLiteManager.decPreviousValue)
            t.column(SQLiteManager.decConfidence)
            t.column(SQLiteManager.decReasoning)
            t.column(SQLiteManager.decStatus, defaultValue: "pending")
            t.column(SQLiteManager.decWasAutoApplied, defaultValue: false)
            t.column(SQLiteManager.decCreatedAt)
            t.column(SQLiteManager.decAppliedAt)
            t.column(SQLiteManager.decReviewId)
            t.column(SQLiteManager.decReviewedBy)
            t.column(SQLiteManager.decReviewedAt)
        })

        // v2: review_queue 表
        try db.run(SQLiteManager.reviewQueue.create(ifNotExists: true) { t in
            t.column(SQLiteManager.revId, primaryKey: true)
            t.column(SQLiteManager.revDecisionId)
            t.column(SQLiteManager.revObjectId)
            t.column(SQLiteManager.revObjectName)
            t.column(SQLiteManager.revPropertyId)
            t.column(SQLiteManager.revPropertyName)
            t.column(SQLiteManager.revAgentType)
            t.column(SQLiteManager.revActionType)
            t.column(SQLiteManager.revProposedValue)
            t.column(SQLiteManager.revCurrentValue)
            t.column(SQLiteManager.revConfidence)
            t.column(SQLiteManager.revReasoning)
            t.column(SQLiteManager.revSampleValues)
            t.column(SQLiteManager.revStatus, defaultValue: "pending")
            t.column(SQLiteManager.revPriority, defaultValue: 0)
            t.column(SQLiteManager.revReviewedBy)
            t.column(SQLiteManager.revReviewedAt)
            t.column(SQLiteManager.revReviewComment)
            t.column(SQLiteManager.revModifiedValue)
            t.column(SQLiteManager.revCreatedAt)
            t.column(SQLiteManager.revExpiresAt)
        })

        // v2: xingji_executions 表
        try db.run(SQLiteManager.xingjiExecutions.create(ifNotExists: true) { t in
            t.column(SQLiteManager.xeId, primaryKey: true)
            t.column(SQLiteManager.xeXingjiId)
            t.column(SQLiteManager.xeXingjiVersion)
            t.column(SQLiteManager.xeTriggerEventId)
            t.column(SQLiteManager.xeTriggerEventType)
            t.column(SQLiteManager.xeCorrelationId)
            t.column(SQLiteManager.xeInputParams)
            t.column(SQLiteManager.xeTargetObjectId)
            t.column(SQLiteManager.xeStatus, defaultValue: "pending")
            t.column(SQLiteManager.xeCurrentCell)
            t.column(SQLiteManager.xeProgress, defaultValue: 0)
            t.column(SQLiteManager.xeOutput)
            t.column(SQLiteManager.xeErrorMessage)
            t.column(SQLiteManager.xeCellsTotal)
            t.column(SQLiteManager.xeCellsCompleted)
            t.column(SQLiteManager.xeDecisionsMade)
            t.column(SQLiteManager.xeDecisionsApplied)
            t.column(SQLiteManager.xeReviewsQueued)
            t.column(SQLiteManager.xeCreatedAt)
            t.column(SQLiteManager.xeStartedAt)
            t.column(SQLiteManager.xeCompletedAt)
            t.column(SQLiteManager.xeDurationMs)
        })

        // 创建索引
        try createIndexes()
    }
    
    private func createIndexes() throws {
        guard let db = db else { return }
        
        // 对象索引
        _ = try? db.run(SQLiteManager.metaObjects.createIndex(SQLiteManager.objStatus, ifNotExists: true))
        _ = try? db.run(SQLiteManager.metaObjects.createIndex(SQLiteManager.objType, ifNotExists: true))
        
        // 属性索引
        _ = try? db.run(SQLiteManager.metaProperties.createIndex(SQLiteManager.propObjectId, ifNotExists: true))
        _ = try? db.run(SQLiteManager.metaProperties.createIndex(SQLiteManager.propSemanticType, ifNotExists: true))
        
        // 关系索引
        _ = try? db.run(SQLiteManager.metaRelations.createIndex(SQLiteManager.relSourceObjectId, ifNotExists: true))
        _ = try? db.run(SQLiteManager.metaRelations.createIndex(SQLiteManager.relTargetObjectId, ifNotExists: true))
        
        // 事件索引（v1）
        _ = try? db.run(SQLiteManager.metaEvents.createIndex(SQLiteManager.evtObjectId, ifNotExists: true))
        _ = try? db.run(SQLiteManager.metaEvents.createIndex(SQLiteManager.evtTimestamp, ifNotExists: true))
        _ = try? db.run(SQLiteManager.metaEvents.createIndex(SQLiteManager.evtType, ifNotExists: true))

        // v2 事件索引
        _ = try? db.run(SQLiteManager.events.createIndex(SQLiteManager.evtV2EventType, ifNotExists: true))
        _ = try? db.run(SQLiteManager.events.createIndex(SQLiteManager.evtV2Timestamp, ifNotExists: true))
        _ = try? db.run(SQLiteManager.events.createIndex(SQLiteManager.evtV2CorrelationId, ifNotExists: true))
        _ = try? db.run(SQLiteManager.events.createIndex(SQLiteManager.evtV2Processed, SQLiteManager.evtV2Timestamp, ifNotExists: true))

        // AI 决策索引
        _ = try? db.run(SQLiteManager.aiDecisions.createIndex(SQLiteManager.decObjectId, ifNotExists: true))
        _ = try? db.run(SQLiteManager.aiDecisions.createIndex(SQLiteManager.decStatus, ifNotExists: true))
        _ = try? db.run(SQLiteManager.aiDecisions.createIndex(SQLiteManager.decAgentType, ifNotExists: true))
        _ = try? db.run(SQLiteManager.aiDecisions.createIndex(SQLiteManager.decConfidence, ifNotExists: true))

        // 审核队列索引
        _ = try? db.run(SQLiteManager.reviewQueue.createIndex(SQLiteManager.revStatus, ifNotExists: true))
        _ = try? db.run(SQLiteManager.reviewQueue.createIndex(SQLiteManager.revObjectId, ifNotExists: true))
        _ = try? db.run(SQLiteManager.reviewQueue.createIndex(SQLiteManager.revCreatedAt, ifNotExists: true))

        // 行技执行索引
        _ = try? db.run(SQLiteManager.xingjiExecutions.createIndex(SQLiteManager.xeXingjiId, ifNotExists: true))
        _ = try? db.run(SQLiteManager.xingjiExecutions.createIndex(SQLiteManager.xeStatus, ifNotExists: true))
        _ = try? db.run(SQLiteManager.xingjiExecutions.createIndex(SQLiteManager.xeCorrelationId, ifNotExists: true))
    }
    
    // MARK: - 错误类型
    
    public enum SQLiteError: Error {
        case connectionFailed
        case insertFailed
        case updateFailed
        case deleteFailed
        case queryFailed
        case notFound
    }
}

// MARK: - 事务助手

extension SQLiteManager {

    /// 在事务中执行一组操作（原子性保证）
    /// 任何一步失败则整体回滚
    public func inTransaction(_ block: (Connection) throws -> Void) throws {
        let db = try getConnection()
        try db.transaction {
            try block(db)
        }
    }

    /// 原子写入：元数据变更 + 审计事件在同一事务中完成
    public func atomicMutateAndAudit(
        mutate: (Connection) throws -> Void,
        auditEventId: String,
        auditEventType: String,
        auditObjectId: String?,
        auditPropertyId: String?,
        auditActorType: String,
        auditActorId: String?,
        auditDescription: String?,
        auditBeforeSnapshot: String?,
        auditAfterSnapshot: String?
    ) throws {
        let db = try getConnection()
        try db.transaction {
            // 1. 执行元数据变更
            try mutate(db)

            // 2. 在同一事务中写入审计事件
            let insert = SQLiteManager.metaEvents.insert(
                SQLiteManager.evtId <- auditEventId,
                SQLiteManager.evtTimestamp <- Date(),
                SQLiteManager.evtType <- auditEventType,
                SQLiteManager.evtObjectId <- auditObjectId,
                SQLiteManager.evtPropertyId <- auditPropertyId,
                SQLiteManager.evtActorType <- auditActorType,
                SQLiteManager.evtActorId <- auditActorId,
                SQLiteManager.evtBeforeSnapshot <- auditBeforeSnapshot,
                SQLiteManager.evtAfterSnapshot <- auditAfterSnapshot,
                SQLiteManager.evtDescription <- auditDescription
            )
            try db.run(insert)
        }
    }
}

// MARK: - JSON 编解码助手

extension SQLiteManager {
    
    static func encodeJSON<T: Encodable>(_ value: T) -> String? {
        guard let data = try? JSONEncoder().encode(value) else { return nil }
        return String(data: data, encoding: .utf8)
    }
    
    static func decodeJSON<T: Decodable>(_ json: String?, as type: T.Type) -> T? {
        guard let json = json, let data = json.data(using: .utf8) else { return nil }
        return try? JSONDecoder().decode(type, from: data)
    }
}
