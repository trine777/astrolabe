// AutoImportXingJi.swift
// 星图 - 自动导入行技
// 版本: v0.2.0

import Foundation

/// 自动导入行技 - 文件拖入后自动执行
public class AutoImportXingJi: XingJiProtocol {
    
    public let id = "xingji.auto_import"
    public let version = "0.2.0"
    public let name = "自动导入行技"
    
    private let csvParser: CSVParser
    private let metaStore: MetaStore
    private let eventBus: EventBus
    
    public init(
        csvParser: CSVParser = CSVParser(),
        metaStore: MetaStore = MetaStore(),
        eventBus: EventBus = .shared
    ) {
        self.csvParser = csvParser
        self.metaStore = metaStore
        self.eventBus = eventBus
    }
    
    public func execute(context: XingJiContext) async throws -> XingJiResult {
        let startTime = Date()
        
        // 1. 从事件中获取文件信息
        guard let fileEvent = context.triggerEvent as? FileDroppedEvent else {
            return .failure("无效的触发事件，需要 FileDroppedEvent")
        }
        
        let filePath = fileEvent.filePath
        let fileURL = URL(fileURLWithPath: filePath)
        
        print("📂 [AutoImport] 开始导入: \(fileEvent.fileName)")
        
        // 2. 解析 CSV 文件
        let parseResult: ParseResult
        do {
            parseResult = try await csvParser.parse(url: fileURL)
        } catch {
            return .failure("CSV 解析失败: \(error.localizedDescription)")
        }
        
        let parseDuration = Int(Date().timeIntervalSince(startTime) * 1000)
        
        // 3. 创建 MetaObject
        let objectName = fileURL.deletingPathExtension().lastPathComponent
        let metaObject = MetaObject(
            name: objectName,
            originalName: fileEvent.fileName,
            objectType: .csvFile,
            description: nil,
            filePath: filePath,
            rowCount: parseResult.rowCount,
            status: .draft
        )
        
        // 4. 创建 MetaProperties
        var properties: [MetaProperty] = []
        for column in parseResult.columns {
            let property = MetaProperty(
                objectId: metaObject.id,
                originalName: column.name,
                dataType: column.inferredType,
                sampleValues: column.sampleValues,
                nullCount: column.nullCount,
                uniqueCount: column.uniqueCount
            )
            properties.append(property)
        }
        
        // 5. 保存到数据库
        do {
            let _ = try await metaStore.createObject(metaObject)
            try await metaStore.saveProperties(properties, objectId: metaObject.id)
        } catch {
            return .failure("保存失败: \(error.localizedDescription)")
        }
        
        // 6. 发布事件
        await eventBus.emitFileParsed(
            correlationId: context.correlationId,
            objectId: metaObject.id,
            columnCount: properties.count,
            rowCount: parseResult.rowCount,
            encoding: parseResult.encoding,
            parseDurationMs: parseDuration
        )
        
        await eventBus.emitObjectCreated(
            correlationId: context.correlationId,
            objectId: metaObject.id,
            objectName: metaObject.name,
            objectType: metaObject.objectType.rawValue,
            sourceFile: filePath
        )
        
        print("✅ [AutoImport] 导入完成: \(objectName) (\(properties.count) 列, \(parseResult.rowCount) 行)")
        
        return XingJiResult(
            success: true,
            output: [
                "object_id": metaObject.id.uuidString,
                "object_name": objectName,
                "column_count": properties.count,
                "row_count": parseResult.rowCount
            ]
        )
    }
}
