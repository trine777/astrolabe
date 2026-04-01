// 星图 (XingTu) - 模块入口
// 星空座的数据地图 - 风隐 OS 数据元数据系统

import Foundation
import Combine

/// 星图主服务
/// 
/// 职责：
/// - 协调五器官完成数据导入和分析
/// - 管理元数据生命周期
/// - 提供世界模型查询接口
///
/// 使用示例：
/// ```swift
/// let xingtu = XingTuService()
/// try await xingtu.initialize()
/// let result = try await xingtu.importCSV(url: fileURL)
/// ```
public class XingTuService {
    
    // MARK: - 依赖（五器官）
    
    /// 星空座：元数据存储
    public let metaStore: MetaStore
    
    /// 影澜轩：事件流
    public let eventStream: MetaEventStream
    
    /// 核心引擎：CSV 解析器
    public let csvParser: CSVParser
    
    // MARK: - 状态
    
    private var isInitialized = false
    private var cancellables = Set<AnyCancellable>()
    
    // MARK: - 初始化
    
    public init(
        sqliteManager: SQLiteManager = .shared
    ) {
        self.metaStore = MetaStore(sqliteManager: sqliteManager)
        self.eventStream = MetaEventStream(sqliteManager: sqliteManager)
        self.csvParser = CSVParser()
    }
    
    /// 初始化服务
    public func initialize() async throws {
        guard !isInitialized else { return }
        
        // 打开数据库
        try SQLiteManager.shared.open()
        
        isInitialized = true
        
        // 订阅事件（用于日志或其他处理）
        setupEventSubscription()
    }
    
    /// 关闭服务
    public func shutdown() {
        cancellables.removeAll()
        SQLiteManager.shared.close()
        isInitialized = false
    }
    
    // MARK: - 数据导入流程
    
    /// 导入 CSV 文件（完整流程）
    ///
    /// 流程：
    /// 1. 解析文件（csv_parse_cell）
    /// 2. AI 语义分析（meta_infer_cell）- 如有 AI 后端
    /// 3. 创建草稿对象
    /// 4. 发送事件
    ///
    /// - Parameter url: CSV 文件路径
    /// - Returns: 导入结果
    public func importCSV(url: URL) async throws -> ImportResult {
        guard isInitialized else {
            throw XingTuError.notInitialized
        }
        
        // 1. 解析文件
        let parseResult = try await csvParser.parse(url: url)
        
        // 2. 创建草稿对象
        let draftObject = MetaObject.fromCSV(
            url: url,
            rowCount: parseResult.rowCount
        )
        
        // 3. 创建属性
        let properties = parseResult.columns.map { col in
            MetaProperty(
                objectId: draftObject.id,
                originalName: col.name,
                dataType: col.inferredType,
                sampleValues: col.sampleValues,
                nullCount: col.nullCount,
                uniqueCount: col.uniqueCount
            )
        }
        
        // 4. 保存到星空座
        let savedObject = try await metaStore.createObject(draftObject)
        try await metaStore.saveProperties(properties, objectId: savedObject.id)
        
        // 5. 发送事件到影澜轩
        await eventStream.emitObjectCreated(
            objectId: savedObject.id,
            by: .system,
            description: "CSV 文件导入: \(url.lastPathComponent)"
        )
        
        return ImportResult(
            object: savedObject,
            properties: properties,
            parseResult: parseResult,
            needsConfirmation: true
        )
    }
    
    /// 确认元数据
    ///
    /// - Parameters:
    ///   - objectId: 对象 ID
    ///   - userId: 确认用户 ID（可选）
    /// - Returns: 确认后的对象
    public func confirmMetadata(
        objectId: UUID,
        userId: String? = nil
    ) async throws -> MetaObject {
        guard var object = try await metaStore.getObject(id: objectId) else {
            throw XingTuError.objectNotFound(objectId)
        }
        
        // 更新状态
        object.confirm(by: userId)
        
        // 保存
        let confirmed = try await metaStore.updateObject(object)
        
        // 发送事件
        await eventStream.emitObjectConfirmed(
            objectId: objectId,
            by: userId
        )
        
        return confirmed
    }
    
    /// 发布对象
    public func publishObject(objectId: UUID) async throws -> MetaObject {
        guard var object = try await metaStore.getObject(id: objectId) else {
            throw XingTuError.objectNotFound(objectId)
        }
        
        guard object.status == .confirmed else {
            throw XingTuError.invalidStatus(current: object.status, expected: .confirmed)
        }
        
        object.publish()
        let published = try await metaStore.updateObject(object)
        
        await eventStream.emit(MetaEvent(
            eventType: .objectPublished,
            objectId: objectId,
            actorType: .user,
            description: "对象已发布"
        ))
        
        return published
    }
    
    // MARK: - 查询
    
    /// 获取所有对象
    public func listObjects(
        status: MetaObject.Status? = nil,
        type: MetaObject.ObjectType? = nil
    ) async throws -> [MetaObject] {
        let filter = ObjectFilter(status: status, objectType: type)
        return try await metaStore.listObjects(filter: filter)
    }
    
    /// 获取对象详情
    public func getObject(id: UUID) async throws -> MetaObject? {
        return try await metaStore.getObject(id: id)
    }
    
    /// 获取对象的属性
    public func getProperties(objectId: UUID) async throws -> [MetaProperty] {
        return try await metaStore.getProperties(objectId: objectId)
    }
    
    /// 获取对象的关系
    public func getRelations(objectId: UUID) async throws -> [MetaRelation] {
        return try await metaStore.getRelations(objectId: objectId)
    }
    
    /// 获取世界模型上下文
    public func getWorldModelContext() async throws -> WorldModelContext {
        return try await metaStore.getWorldModelContext()
    }
    
    /// 获取对象的事件历史
    public func getObjectHistory(objectId: UUID) async throws -> [MetaEvent] {
        return try await eventStream.getObjectHistory(objectId: objectId)
    }
    
    // MARK: - 私有方法
    
    private func setupEventSubscription() {
        eventStream.subscribe(filter: nil)
            .sink { event in
                // 可以在这里添加日志或其他处理
                #if DEBUG
                print("[XingTu] Event: \(event.eventType.displayName) - \(event.description ?? "")")
                #endif
            }
            .store(in: &cancellables)
    }
}

// MARK: - 导入结果

/// 导入结果
public struct ImportResult {
    public let object: MetaObject
    public let properties: [MetaProperty]
    public let parseResult: ParseResult
    public let needsConfirmation: Bool
    
    public init(
        object: MetaObject,
        properties: [MetaProperty],
        parseResult: ParseResult,
        needsConfirmation: Bool
    ) {
        self.object = object
        self.properties = properties
        self.parseResult = parseResult
        self.needsConfirmation = needsConfirmation
    }
}

// MARK: - 错误

/// 星图错误
public enum XingTuError: Error, LocalizedError {
    case notInitialized
    case objectNotFound(UUID)
    case invalidStatus(current: MetaObject.Status, expected: MetaObject.Status)
    case importFailed(String)
    case analysisFailed(String)
    
    public var errorDescription: String? {
        switch self {
        case .notInitialized:
            return "星图服务未初始化"
        case .objectNotFound(let id):
            return "对象不存在: \(id)"
        case .invalidStatus(let current, let expected):
            return "状态无效: 当前 \(current.displayName), 需要 \(expected.displayName)"
        case .importFailed(let msg):
            return "导入失败: \(msg)"
        case .analysisFailed(let msg):
            return "分析失败: \(msg)"
        }
    }
}

// MARK: - 版本信息

public struct XingTuInfo {
    public static let version = "0.1.0"
    public static let name = "星图"
    public static let englishName = "XingTu"
    public static let description = "星空座的数据地图 - 风隐 OS 数据元数据系统"
    public static let organ = "星空座 (Xingkongzuo)"
}
