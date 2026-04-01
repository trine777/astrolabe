// 星图 (XingTu) - 元数据存储
// 归属: 星空座 (Xingkongzuo)

import Foundation
import SQLite

/// 星空座：元数据存储协议
public protocol MetaStoreProtocol {
    // 元数据对象 CRUD
    func createObject(_ object: MetaObject) async throws -> MetaObject
    func getObject(id: UUID) async throws -> MetaObject?
    func updateObject(_ object: MetaObject) async throws -> MetaObject
    func deleteObject(id: UUID) async throws
    func listObjects(filter: ObjectFilter?) async throws -> [MetaObject]
    
    // 元数据属性
    func saveProperties(_ properties: [MetaProperty], objectId: UUID) async throws
    func getProperties(objectId: UUID) async throws -> [MetaProperty]
    func updateProperty(_ property: MetaProperty) async throws -> MetaProperty
    
    // 元数据关系
    func createRelation(_ relation: MetaRelation) async throws -> MetaRelation
    func getRelations(objectId: UUID) async throws -> [MetaRelation]
    func confirmRelation(id: UUID) async throws -> MetaRelation
    
    // 世界模型
    func getWorldModelContext() async throws -> WorldModelContext
}

/// 对象过滤器
public struct ObjectFilter {
    public var status: MetaObject.Status?
    public var objectType: MetaObject.ObjectType?
    public var tags: [String]?
    public var searchText: String?
    
    public init(
        status: MetaObject.Status? = nil,
        objectType: MetaObject.ObjectType? = nil,
        tags: [String]? = nil,
        searchText: String? = nil
    ) {
        self.status = status
        self.objectType = objectType
        self.tags = tags
        self.searchText = searchText
    }
}

/// 世界模型上下文（供 AI 使用）
public struct WorldModelContext: Codable {
    public var objects: [MetaObjectSummary]
    public var relations: [MetaRelationSummary]
    public var metrics: [MetricDefSummary]
    
    public init(
        objects: [MetaObjectSummary] = [],
        relations: [MetaRelationSummary] = [],
        metrics: [MetricDefSummary] = []
    ) {
        self.objects = objects
        self.relations = relations
        self.metrics = metrics
    }
    
    /// 生成 AI 可读的上下文描述
    public func toPromptContext() -> String {
        var lines: [String] = []
        
        if !objects.isEmpty {
            lines.append("## 已有数据对象")
            for obj in objects {
                var line = "- \(obj.name) (\(obj.objectType))"
                if let desc = obj.description {
                    line += ": \(desc)"
                }
                if let rows = obj.rowCount {
                    line += " [\(rows) 行]"
                }
                lines.append(line)
            }
        }
        
        if !relations.isEmpty {
            lines.append("\n## 已有关系")
            for rel in relations {
                lines.append("- \(rel.relationName ?? "关联"): \(rel.relationType)")
            }
        }
        
        if !metrics.isEmpty {
            lines.append("\n## 已有指标")
            for met in metrics {
                var line = "- \(met.displayName)"
                if let unit = met.unit {
                    line += " (\(unit))"
                }
                lines.append(line)
            }
        }
        
        return lines.isEmpty ? "暂无已有数据" : lines.joined(separator: "\n")
    }
}

/// 星空座：元数据存储实现
public class MetaStore: MetaStoreProtocol {
    
    private let sqliteManager: SQLiteManager
    
    public init(sqliteManager: SQLiteManager = .shared) {
        self.sqliteManager = sqliteManager
    }
    
    // MARK: - 元数据对象 CRUD
    
    public func createObject(_ object: MetaObject) async throws -> MetaObject {
        let db = try sqliteManager.getConnection()
        
        let insert = SQLiteManager.metaObjects.insert(
            SQLiteManager.objId <- object.id.uuidString,
            SQLiteManager.objName <- object.name,
            SQLiteManager.objOriginalName <- object.originalName,
            SQLiteManager.objType <- object.objectType.rawValue,
            SQLiteManager.objDescription <- object.description,
            SQLiteManager.objFilePath <- object.filePath,
            SQLiteManager.objRowCount <- object.rowCount,
            SQLiteManager.objStatus <- object.status.rawValue,
            SQLiteManager.objTags <- SQLiteManager.encodeJSON(object.tags),
            SQLiteManager.objCreatedAt <- object.createdAt,
            SQLiteManager.objUpdatedAt <- object.updatedAt,
            SQLiteManager.objConfirmedAt <- object.confirmedAt,
            SQLiteManager.objConfirmedBy <- object.confirmedBy
        )
        
        try db.run(insert)
        return object
    }
    
    public func getObject(id: UUID) async throws -> MetaObject? {
        let db = try sqliteManager.getConnection()
        
        let query = SQLiteManager.metaObjects.filter(SQLiteManager.objId == id.uuidString)
        
        guard let row = try db.pluck(query) else {
            return nil
        }
        
        return try parseObjectRow(row)
    }
    
    public func updateObject(_ object: MetaObject) async throws -> MetaObject {
        // 获取变更前快照用于审计
        let before = try await getObject(id: object.id)
        let beforeSnapshot = SQLiteManager.encodeJSON(before?.summary)

        try sqliteManager.atomicMutateAndAudit(
            mutate: { db in
                let target = SQLiteManager.metaObjects.filter(SQLiteManager.objId == object.id.uuidString)
                try db.run(target.update(
                    SQLiteManager.objName <- object.name,
                    SQLiteManager.objDescription <- object.description,
                    SQLiteManager.objStatus <- object.status.rawValue,
                    SQLiteManager.objTags <- SQLiteManager.encodeJSON(object.tags),
                    SQLiteManager.objUpdatedAt <- Date(),
                    SQLiteManager.objConfirmedAt <- object.confirmedAt,
                    SQLiteManager.objConfirmedBy <- object.confirmedBy
                ))
            },
            auditEventId: UUID().uuidString,
            auditEventType: "object.updated",
            auditObjectId: object.id.uuidString,
            auditPropertyId: nil,
            auditActorType: "system",
            auditActorId: nil,
            auditDescription: "对象更新: \(object.name)",
            auditBeforeSnapshot: beforeSnapshot,
            auditAfterSnapshot: SQLiteManager.encodeJSON(object.summary)
        )

        return object
    }
    
    public func deleteObject(id: UUID) async throws {
        let db = try sqliteManager.getConnection()
        
        let target = SQLiteManager.metaObjects.filter(SQLiteManager.objId == id.uuidString)
        try db.run(target.delete())
    }
    
    public func listObjects(filter: ObjectFilter?) async throws -> [MetaObject] {
        let db = try sqliteManager.getConnection()
        
        var query = SQLiteManager.metaObjects
        
        if let filter = filter {
            if let status = filter.status {
                query = query.filter(SQLiteManager.objStatus == status.rawValue)
            }
            if let objectType = filter.objectType {
                query = query.filter(SQLiteManager.objType == objectType.rawValue)
            }
            if let searchText = filter.searchText, !searchText.isEmpty {
                query = query.filter(
                    SQLiteManager.objName.like("%\(searchText)%") ||
                    SQLiteManager.objDescription.like("%\(searchText)%")
                )
            }
        }
        
        query = query.order(SQLiteManager.objUpdatedAt.desc)
        
        var objects: [MetaObject] = []
        for row in try db.prepare(query) {
            if let object = try? parseObjectRow(row) {
                objects.append(object)
            }
        }
        
        return objects
    }
    
    // MARK: - 元数据属性
    
    public func saveProperties(_ properties: [MetaProperty], objectId: UUID) async throws {
        let db = try sqliteManager.getConnection()
        
        for prop in properties {
            let insert = SQLiteManager.metaProperties.insert(or: .replace,
                SQLiteManager.propId <- prop.id.uuidString,
                SQLiteManager.propObjectId <- objectId.uuidString,
                SQLiteManager.propOriginalName <- prop.originalName,
                SQLiteManager.propDataType <- prop.dataType.rawValue,
                SQLiteManager.propSampleValues <- SQLiteManager.encodeJSON(prop.sampleValues),
                SQLiteManager.propNullCount <- prop.nullCount,
                SQLiteManager.propUniqueCount <- prop.uniqueCount,
                SQLiteManager.propDisplayName <- prop.displayName,
                SQLiteManager.propDescription <- prop.description,
                SQLiteManager.propSemanticType <- prop.semanticType?.rawValue,
                SQLiteManager.propUnit <- prop.unit,
                SQLiteManager.propFormat <- prop.format,
                SQLiteManager.propBusinessRules <- prop.businessRules,
                SQLiteManager.propVisualPreference <- SQLiteManager.encodeJSON(prop.visualPreference),
                SQLiteManager.propUserConfirmedAt <- prop.userConfirmedAt,
                SQLiteManager.propAIInferred <- SQLiteManager.encodeJSON(prop.aiInferred)
            )
            try db.run(insert)
        }
    }
    
    public func getProperties(objectId: UUID) async throws -> [MetaProperty] {
        let db = try sqliteManager.getConnection()
        
        let query = SQLiteManager.metaProperties.filter(
            SQLiteManager.propObjectId == objectId.uuidString
        )
        
        var properties: [MetaProperty] = []
        for row in try db.prepare(query) {
            if let prop = try? parsePropertyRow(row, objectId: objectId) {
                properties.append(prop)
            }
        }
        
        return properties
    }
    
    public func getProperty(_ propertyId: UUID) async throws -> MetaProperty? {
        let db = try sqliteManager.getConnection()
        
        let query = SQLiteManager.metaProperties.filter(
            SQLiteManager.propId == propertyId.uuidString
        )
        
        for row in try db.prepare(query) {
            let objectIdStr = row[SQLiteManager.propObjectId]
            if let objectId = UUID(uuidString: objectIdStr) {
                return try? parsePropertyRow(row, objectId: objectId)
            }
        }
        
        return nil
    }
    
    public func updateProperty(_ property: MetaProperty) async throws -> MetaProperty {
        // 获取变更前快照用于审计
        let before = try await getProperty(property.id)
        let beforeSnapshot = SQLiteManager.encodeJSON(before?.summary)

        try sqliteManager.atomicMutateAndAudit(
            mutate: { db in
                let target = SQLiteManager.metaProperties.filter(
                    SQLiteManager.propId == property.id.uuidString
                )
                try db.run(target.update(
                    SQLiteManager.propDisplayName <- property.displayName,
                    SQLiteManager.propDescription <- property.description,
                    SQLiteManager.propSemanticType <- property.semanticType?.rawValue,
                    SQLiteManager.propUnit <- property.unit,
                    SQLiteManager.propFormat <- property.format,
                    SQLiteManager.propBusinessRules <- property.businessRules,
                    SQLiteManager.propVisualPreference <- SQLiteManager.encodeJSON(property.visualPreference),
                    SQLiteManager.propUserConfirmedAt <- property.userConfirmedAt
                ))
            },
            auditEventId: UUID().uuidString,
            auditEventType: "property.updated",
            auditObjectId: property.objectId.uuidString,
            auditPropertyId: property.id.uuidString,
            auditActorType: "system",
            auditActorId: nil,
            auditDescription: "属性更新: \(property.displayName)",
            auditBeforeSnapshot: beforeSnapshot,
            auditAfterSnapshot: SQLiteManager.encodeJSON(property.summary)
        )

        return property
    }
    
    // MARK: - 元数据关系
    
    public func createRelation(_ relation: MetaRelation) async throws -> MetaRelation {
        let db = try sqliteManager.getConnection()
        
        let insert = SQLiteManager.metaRelations.insert(
            SQLiteManager.relId <- relation.id.uuidString,
            SQLiteManager.relSourceObjectId <- relation.sourceObjectId.uuidString,
            SQLiteManager.relSourcePropertyId <- relation.sourcePropertyId.uuidString,
            SQLiteManager.relTargetObjectId <- relation.targetObjectId.uuidString,
            SQLiteManager.relTargetPropertyId <- relation.targetPropertyId.uuidString,
            SQLiteManager.relType <- relation.relationType.rawValue,
            SQLiteManager.relName <- relation.relationName,
            SQLiteManager.relDescription <- relation.description,
            SQLiteManager.relIsAIInferred <- relation.isAIInferred,
            SQLiteManager.relConfidence <- relation.confidence,
            SQLiteManager.relIsConfirmed <- relation.isConfirmed,
            SQLiteManager.relConfirmedAt <- relation.confirmedAt
        )
        
        try db.run(insert)
        return relation
    }
    
    public func getRelations(objectId: UUID) async throws -> [MetaRelation] {
        let db = try sqliteManager.getConnection()
        
        let query = SQLiteManager.metaRelations.filter(
            SQLiteManager.relSourceObjectId == objectId.uuidString ||
            SQLiteManager.relTargetObjectId == objectId.uuidString
        )
        
        var relations: [MetaRelation] = []
        for row in try db.prepare(query) {
            if let rel = try? parseRelationRow(row) {
                relations.append(rel)
            }
        }
        
        return relations
    }
    
    public func confirmRelation(id: UUID) async throws -> MetaRelation {
        let db = try sqliteManager.getConnection()
        
        let target = SQLiteManager.metaRelations.filter(SQLiteManager.relId == id.uuidString)
        
        try db.run(target.update(
            SQLiteManager.relIsConfirmed <- true,
            SQLiteManager.relConfirmedAt <- Date()
        ))
        
        // 重新获取
        guard let row = try db.pluck(target),
              let relation = try? parseRelationRow(row) else {
            throw SQLiteManager.SQLiteError.notFound
        }
        
        return relation
    }
    
    // MARK: - 世界模型
    
    public func getWorldModelContext() async throws -> WorldModelContext {
        let objects = try await listObjects(filter: ObjectFilter(status: .published))
        let objectSummaries = objects.map { $0.summary }
        
        // 获取所有已确认的关系
        var allRelations: [MetaRelationSummary] = []
        for obj in objects {
            let rels = try await getRelations(objectId: obj.id)
            allRelations.append(contentsOf: rels.filter { $0.isConfirmed }.map { $0.summary })
        }
        
        // TODO: 获取指标定义
        let metrics: [MetricDefSummary] = []
        
        return WorldModelContext(
            objects: objectSummaries,
            relations: allRelations,
            metrics: metrics
        )
    }
    
    // MARK: - 行解析助手
    
    private func parseObjectRow(_ row: Row) throws -> MetaObject {
        let id = UUID(uuidString: row[SQLiteManager.objId])!
        let tags: [String] = SQLiteManager.decodeJSON(row[SQLiteManager.objTags], as: [String].self) ?? []
        
        return MetaObject(
            id: id,
            name: row[SQLiteManager.objName],
            originalName: row[SQLiteManager.objOriginalName],
            objectType: MetaObject.ObjectType(rawValue: row[SQLiteManager.objType]) ?? .csvFile,
            description: row[SQLiteManager.objDescription],
            filePath: row[SQLiteManager.objFilePath],
            rowCount: row[SQLiteManager.objRowCount],
            tags: tags,
            status: MetaObject.Status(rawValue: row[SQLiteManager.objStatus]) ?? .draft,
            createdAt: row[SQLiteManager.objCreatedAt],
            updatedAt: row[SQLiteManager.objUpdatedAt],
            confirmedAt: row[SQLiteManager.objConfirmedAt],
            confirmedBy: row[SQLiteManager.objConfirmedBy]
        )
    }
    
    private func parsePropertyRow(_ row: Row, objectId: UUID) throws -> MetaProperty {
        let id = UUID(uuidString: row[SQLiteManager.propId])!
        let sampleValues: [String] = SQLiteManager.decodeJSON(row[SQLiteManager.propSampleValues], as: [String].self) ?? []
        let visualPref = SQLiteManager.decodeJSON(row[SQLiteManager.propVisualPreference], as: MetaProperty.VisualPreference.self)
        let aiInferred = SQLiteManager.decodeJSON(row[SQLiteManager.propAIInferred], as: MetaProperty.AIInferredInfo.self)
        
        return MetaProperty(
            id: id,
            objectId: objectId,
            originalName: row[SQLiteManager.propOriginalName],
            dataType: MetaProperty.DataType(rawValue: row[SQLiteManager.propDataType]) ?? .unknown,
            sampleValues: sampleValues,
            nullCount: row[SQLiteManager.propNullCount],
            uniqueCount: row[SQLiteManager.propUniqueCount],
            displayName: row[SQLiteManager.propDisplayName],
            description: row[SQLiteManager.propDescription],
            semanticType: row[SQLiteManager.propSemanticType].flatMap { MetaProperty.SemanticType(rawValue: $0) },
            unit: row[SQLiteManager.propUnit],
            format: row[SQLiteManager.propFormat],
            businessRules: row[SQLiteManager.propBusinessRules],
            visualPreference: visualPref,
            userConfirmedAt: row[SQLiteManager.propUserConfirmedAt],
            aiInferred: aiInferred
        )
    }
    
    private func parseRelationRow(_ row: Row) throws -> MetaRelation {
        let id = UUID(uuidString: row[SQLiteManager.relId])!
        
        return MetaRelation(
            id: id,
            sourceObjectId: UUID(uuidString: row[SQLiteManager.relSourceObjectId])!,
            sourcePropertyId: UUID(uuidString: row[SQLiteManager.relSourcePropertyId])!,
            targetObjectId: UUID(uuidString: row[SQLiteManager.relTargetObjectId])!,
            targetPropertyId: UUID(uuidString: row[SQLiteManager.relTargetPropertyId])!,
            relationType: MetaRelation.RelationType(rawValue: row[SQLiteManager.relType]) ?? .oneToMany,
            relationName: row[SQLiteManager.relName],
            description: row[SQLiteManager.relDescription],
            isAIInferred: row[SQLiteManager.relIsAIInferred],
            confidence: row[SQLiteManager.relConfidence],
            isConfirmed: row[SQLiteManager.relIsConfirmed],
            confirmedAt: row[SQLiteManager.relConfirmedAt]
        )
    }
}
