// XingTu 命令行测试工具
// 用于验证星图模块的核心功能

import Foundation
import XingTu

// MARK: - 测试入口

@main
struct XingTuCLI {
    static func main() async {
        print("═══════════════════════════════════════════════════════════")
        print("  🌟 星图 (XingTu) 功能测试")
        print("  版本: \(XingTuInfo.version)")
        print("═══════════════════════════════════════════════════════════")
        print()
        
        do {
            // 1. 测试 CSV 解析
            try await testCSVParser()
            
            // 2. 测试数据库存储
            try await testSQLiteManager()
            
            // 3. 测试 MetaStore
            try await testMetaStore()
            
            // 4. 测试事件流
            try await testEventStream()
            
            // 5. 测试完整流程
            try await testFullWorkflow()
            
            print()
            print("═══════════════════════════════════════════════════════════")
            print("  ✅ 所有测试通过！")
            print("═══════════════════════════════════════════════════════════")
            
        } catch {
            print()
            print("═══════════════════════════════════════════════════════════")
            print("  ❌ 测试失败: \(error)")
            print("═══════════════════════════════════════════════════════════")
        }
    }
    
    // MARK: - CSV 解析测试
    
    static func testCSVParser() async throws {
        print("┌─────────────────────────────────────────────────────────┐")
        print("│ 测试 1: CSV 解析器                                      │")
        print("└─────────────────────────────────────────────────────────┘")
        
        let parser = CSVParser()
        
        // 使用内存测试
        let csvContent = """
        id,name,email,age,created_at,amount
        1,张三,zhangsan@example.com,28,2024-01-15,1500.50
        2,李四,lisi@example.com,35,2024-02-20,2300.00
        3,王五,wangwu@example.com,42,2024-03-10,890.75
        """
        
        let tempURL = FileManager.default.temporaryDirectory.appendingPathComponent("test_\(UUID().uuidString).csv")
        try csvContent.write(to: tempURL, atomically: true, encoding: .utf8)
        defer { try? FileManager.default.removeItem(at: tempURL) }
        
        let result = try await parser.parse(url: tempURL)
        
        print("  ✓ 解析成功!")
        print("    - 编码: \(result.encoding)")
        print("    - 行数: \(result.rowCount)")
        print("    - 列数: \(result.columns.count)")
        print("    - 列信息:")
        for col in result.columns {
            print("      • \(col.name): \(col.inferredType.displayName) (空值: \(col.nullCount), 唯一: \(col.uniqueCount))")
        }
    }
    
    // MARK: - SQLite 测试
    
    static func testSQLiteManager() async throws {
        print()
        print("┌─────────────────────────────────────────────────────────┐")
        print("│ 测试 2: SQLite 数据库管理                               │")
        print("└─────────────────────────────────────────────────────────┘")
        
        // 使用临时数据库
        let tempDir = FileManager.default.temporaryDirectory
        let dbPath = tempDir.appendingPathComponent("xingtu_test_\(UUID().uuidString).sqlite").path
        
        let manager = SQLiteManager(path: dbPath)
        try manager.open()
        print("  ✓ 数据库创建成功: \(dbPath)")
        
        // 验证表存在
        let db = try manager.getConnection()
        
        // 简单查询测试
        let count = try db.scalar("SELECT COUNT(*) FROM meta_objects") as? Int64 ?? 0
        print("  ✓ meta_objects 表存在，当前记录数: \(count)")
        
        // 关闭并清理
        manager.close()
        try FileManager.default.removeItem(atPath: dbPath)
        print("  ✓ 测试数据库已清理")
    }
    
    // MARK: - MetaStore 测试
    
    static func testMetaStore() async throws {
        print()
        print("┌─────────────────────────────────────────────────────────┐")
        print("│ 测试 3: MetaStore (星空座存储)                          │")
        print("└─────────────────────────────────────────────────────────┘")
        
        let tempDir = FileManager.default.temporaryDirectory
        let dbPath = tempDir.appendingPathComponent("xingtu_test_\(UUID().uuidString).sqlite").path
        let manager = SQLiteManager(path: dbPath)
        try manager.open()
        
        let store = MetaStore(sqliteManager: manager)
        
        // 创建测试对象
        let testObject = MetaObject(
            name: "测试数据源",
            originalName: "test_data.csv",
            objectType: .csvFile,
            description: "这是一个测试用的数据源",
            filePath: "/tmp/test.csv",
            rowCount: 100
        )
        
        // 保存
        let saved = try await store.createObject(testObject)
        print("  ✓ 对象保存成功: \(saved.id)")
        
        // 读取
        if let loaded = try await store.getObject(id: saved.id) {
            print("  ✓ 对象读取成功: \(loaded.name)")
        }
        
        // 创建属性
        let prop = MetaProperty(
            objectId: saved.id,
            originalName: "user_id",
            dataType: .integer,
            sampleValues: ["1", "2", "3"],
            nullCount: 0,
            uniqueCount: 100,
            displayName: "用户ID",
            description: "用户唯一标识符",
            semanticType: .uniqueId
        )
        
        try await store.saveProperties([prop], objectId: saved.id)
        print("  ✓ 属性保存成功: \(prop.originalName)")
        
        // 读取属性
        let props = try await store.getProperties(objectId: saved.id)
        print("  ✓ 属性读取成功，数量: \(props.count)")
        
        // 获取世界模型上下文
        let context = try await store.getWorldModelContext()
        print("  ✓ 世界模型上下文: \(context.objects.count) 个对象")
        
        // 清理
        manager.close()
        try FileManager.default.removeItem(atPath: dbPath)
        print("  ✓ 测试数据已清理")
    }
    
    // MARK: - 事件流测试
    
    static func testEventStream() async throws {
        print()
        print("┌─────────────────────────────────────────────────────────┐")
        print("│ 测试 4: MetaEventStream (影澜轩事件流)                  │")
        print("└─────────────────────────────────────────────────────────┘")
        
        let tempDir = FileManager.default.temporaryDirectory
        let dbPath = tempDir.appendingPathComponent("xingtu_test_\(UUID().uuidString).sqlite").path
        let manager = SQLiteManager(path: dbPath)
        try manager.open()
        
        let stream = MetaEventStream(sqliteManager: manager)
        
        let objectId = UUID()
        
        // 发送事件
        await stream.emitObjectCreated(
            objectId: objectId,
            by: .system,
            description: "测试对象创建"
        )
        print("  ✓ 事件发送成功: objectCreated")
        
        await stream.emitPropertyUpdated(
            objectId: objectId,
            propertyId: UUID(),
            by: .user,
            before: nil,
            after: "new_value"
        )
        print("  ✓ 事件发送成功: propertyUpdated")
        
        // 查询历史
        let history = try await stream.getObjectHistory(objectId: objectId)
        print("  ✓ 事件历史查询成功，数量: \(history.count)")
        
        for event in history {
            print("    • [\(event.eventType.displayName)] \(event.description ?? "-")")
        }
        
        // 清理
        manager.close()
        try FileManager.default.removeItem(atPath: dbPath)
        print("  ✓ 测试数据已清理")
    }
    
    // MARK: - 完整流程测试
    
    static func testFullWorkflow() async throws {
        print()
        print("┌─────────────────────────────────────────────────────────┐")
        print("│ 测试 5: XingTuService 完整流程                          │")
        print("└─────────────────────────────────────────────────────────┘")
        
        let tempDir = FileManager.default.temporaryDirectory
        let dbPath = tempDir.appendingPathComponent("xingtu_full_test_\(UUID().uuidString).sqlite").path
        
        // 创建自定义 SQLiteManager
        let manager = SQLiteManager(path: dbPath)
        try manager.open()
        
        // 创建服务
        let service = XingTuService(sqliteManager: manager)
        try await service.initialize()
        print("  ✓ XingTuService 初始化成功")
        
        // 创建测试 CSV
        let csvContent = """
        order_id,customer_name,product,quantity,price,order_date
        ORD001,张三,iPhone 15,1,7999.00,2024-01-15
        ORD002,李四,MacBook Pro,1,14999.00,2024-01-16
        ORD003,王五,AirPods Pro,2,1899.00,2024-01-17
        ORD004,张三,iPad Air,1,4799.00,2024-01-18
        ORD005,赵六,Apple Watch,1,2999.00,2024-01-19
        """
        
        let csvURL = tempDir.appendingPathComponent("orders_test_\(UUID().uuidString).csv")
        try csvContent.write(to: csvURL, atomically: true, encoding: .utf8)
        defer { try? FileManager.default.removeItem(at: csvURL) }
        print("  ✓ 测试 CSV 文件创建成功")
        
        // 导入 CSV
        let result = try await service.importCSV(url: csvURL)
        print("  ✓ CSV 导入成功!")
        print("    - 对象ID: \(result.object.id)")
        print("    - 对象名: \(result.object.name)")
        print("    - 状态: \(result.object.status.displayName)")
        print("    - 列数: \(result.properties.count)")
        print("    - 推断的列类型:")
        for prop in result.properties {
            print("      • \(prop.originalName): \(prop.dataType.displayName)")
        }
        
        // 确认元数据
        let confirmed = try await service.confirmMetadata(objectId: result.object.id, userId: "test_user")
        print("  ✓ 元数据确认成功，状态: \(confirmed.status.displayName)")
        
        // 验证确认后的状态
        let objects = try await service.listObjects()
        print("  ✓ 对象列表查询成功，共 \(objects.count) 个对象")
        
        // 查询事件历史
        let events = try await service.getObjectHistory(objectId: result.object.id)
        print("  ✓ 事件历史 (\(events.count) 条):")
        for event in events.prefix(5) {
            print("    • [\(event.eventType.displayName)] \(event.description ?? "-")")
        }
        
        // 获取世界模型
        let worldModel = try await service.getWorldModelContext()
        print("  ✓ 世界模型: \(worldModel.objects.count) 个对象")
        
        // 关闭服务
        service.shutdown()
        print("  ✓ 服务已关闭")
        
        // 清理
        try FileManager.default.removeItem(atPath: dbPath)
        print("  ✓ 测试数据已清理")
    }
}
