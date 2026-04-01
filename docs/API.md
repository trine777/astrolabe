# 星图 (XingTu) 接口协议

> 版本: v0.1.0 | 协议: Swift Protocol + REST-like

## 1. 概述

星图 API 分为两层：
1. **Swift Protocol**：模块内部接口，用于器官协作
2. **REST-like API**：外部调用接口（未来 MCP 集成）

## 2. 器官协作协议

### 2.1 星空座协议（MetaStore）

```swift
/// 星空座：元数据存储协议
protocol MetaStoreProtocol {
    
    // === 元数据对象 CRUD ===
    
    /// 创建元数据对象
    func createObject(_ object: MetaObject) async throws -> MetaObject
    
    /// 获取元数据对象
    func getObject(id: UUID) async throws -> MetaObject?
    
    /// 更新元数据对象
    func updateObject(_ object: MetaObject) async throws -> MetaObject
    
    /// 删除元数据对象
    func deleteObject(id: UUID) async throws
    
    /// 列出所有对象
    func listObjects(filter: ObjectFilter?) async throws -> [MetaObject]
    
    // === 元数据属性 ===
    
    /// 批量保存属性
    func saveProperties(_ properties: [MetaProperty], objectId: UUID) async throws
    
    /// 获取对象的所有属性
    func getProperties(objectId: UUID) async throws -> [MetaProperty]
    
    /// 更新单个属性
    func updateProperty(_ property: MetaProperty) async throws -> MetaProperty
    
    // === 元数据关系 ===
    
    /// 创建关系
    func createRelation(_ relation: MetaRelation) async throws -> MetaRelation
    
    /// 获取对象的所有关系
    func getRelations(objectId: UUID) async throws -> [MetaRelation]
    
    /// 确认关系
    func confirmRelation(id: UUID) async throws -> MetaRelation
    
    // === 世界模型查询 ===
    
    /// 获取世界模型上下文（供 AI 使用）
    func getWorldModelContext() async throws -> WorldModelContext
    
    /// 搜索相关对象
    func searchObjects(query: String) async throws -> [MetaObject]
}

/// 对象过滤器
struct ObjectFilter {
    var status: MetaObject.Status?
    var objectType: MetaObject.ObjectType?
    var tags: [String]?
    var searchText: String?
}

/// 世界模型上下文
struct WorldModelContext {
    var objects: [MetaObjectSummary]
    var relations: [MetaRelationSummary]
    var metrics: [MetricDefSummary]
}
```

### 2.2 语界枢协议（InputChannel）

```swift
/// 语界枢：输入通道协议
protocol InputChannelProtocol {
    
    /// 接收文件（拖放）
    func receiveFile(url: URL) async throws -> FileReceiveResult
    
    /// 接收自然语言输入
    func receiveNaturalLanguage(_ text: String) async throws -> NLParseResult
    
    /// 呈现元数据编辑器
    func presentMetaEditor(object: MetaObject) async throws -> MetaEditResult
    
    /// 呈现确认对话框
    func presentConfirmation(message: String, options: [ConfirmOption]) async throws -> ConfirmOption
}

struct FileReceiveResult {
    let url: URL
    let fileType: String
    let size: Int64
}

struct NLParseResult {
    let intent: QueryIntent
    let entities: [Entity]
    let confidence: Double
}

struct MetaEditResult {
    let confirmed: Bool
    let edits: [MetaEdit]
}

struct MetaEdit {
    let propertyId: UUID
    let field: String
    let oldValue: String?
    let newValue: String
}
```

### 2.3 影澜轩协议（EventStream）

```swift
/// 影澜轩：事件流协议
protocol EventStreamProtocol {
    
    /// 发送事件
    func emit(_ event: MetaEvent) async
    
    /// 订阅事件
    func subscribe(filter: EventFilter) -> AsyncStream<MetaEvent>
    
    /// 获取历史事件
    func getHistory(filter: EventFilter, limit: Int) async throws -> [MetaEvent]
    
    /// 获取对象的变更历史
    func getObjectHistory(objectId: UUID) async throws -> [MetaEvent]
}

struct EventFilter {
    var eventTypes: [MetaEvent.EventType]?
    var objectId: UUID?
    var actorType: MetaEvent.ActorType?
    var since: Date?
}
```

### 2.4 核心引擎协议

```swift
/// CSV 解析器协议
protocol CSVParserProtocol {
    
    /// 解析 CSV 文件
    func parse(url: URL) async throws -> ParseResult
    
    /// 预览数据
    func preview(url: URL, rows: Int) async throws -> [[String]]
    
    /// 推断数据类型
    func inferTypes(columns: [String], samples: [[String]]) -> [DataTypeInference]
}

struct ParseResult {
    let columns: [ColumnInfo]
    let rowCount: Int
    let sampleData: [[String]]
    let encoding: String
}

struct ColumnInfo {
    let name: String
    let inferredType: MetaProperty.DataType
    let nullCount: Int
    let uniqueCount: Int
    let sampleValues: [String]
}

struct DataTypeInference {
    let columnIndex: Int
    let dataType: MetaProperty.DataType
    let confidence: Double
}
```

```swift
/// AI 分析器协议
protocol AIAnalyzerProtocol {
    
    /// 分析 schema，推断语义类型
    func analyzeSchema(_ schema: SchemaInfo, context: WorldModelContext?) async throws -> AIAnalysisResult
    
    /// 推断对象间关系
    func inferRelations(objects: [MetaObject]) async throws -> [RelationInference]
    
    /// 自然语言转 SQL
    func translateToSQL(query: String, context: WorldModelContext) async throws -> SQLTranslation
}

struct SchemaInfo {
    let fileName: String
    let columns: [ColumnInfo]
    let rowCount: Int
}

struct AIAnalysisResult {
    let objectSuggestion: ObjectSuggestion
    let propertySuggestions: [PropertySuggestion]
    let potentialRelations: [RelationSuggestion]
    let dataQualityNotes: [String]
}

struct PropertySuggestion {
    let originalName: String
    let displayName: String
    let semanticType: MetaProperty.SemanticType
    let description: String?
    let unit: String?
    let confidence: Double
    let reasoning: String
}

struct RelationInference {
    let sourceObjectId: UUID
    let sourcePropertyId: UUID
    let targetObjectId: UUID
    let targetPropertyId: UUID
    let relationType: MetaRelation.RelationType
    let confidence: Double
    let reasoning: String
}

struct SQLTranslation {
    let sql: String
    let explanation: String
    let referencedObjects: [UUID]
}
```

```swift
/// 查询引擎协议
protocol QueryEngineProtocol {
    
    /// 执行 SQL 查询
    func executeSQL(_ sql: String) async throws -> QueryResult
    
    /// 执行自然语言查询
    func executeNL(_ query: String, context: WorldModelContext) async throws -> QueryResult
    
    /// 获取对象数据预览
    func preview(objectId: UUID, limit: Int) async throws -> QueryResult
}

struct QueryResult {
    let columns: [String]
    let rows: [[Any]]
    let rowCount: Int
    let executionTime: TimeInterval
}
```

## 3. 服务入口

### 3.1 XingTu 服务

```swift
/// 星图主服务
class XingTuService {
    
    // 依赖
    let metaStore: MetaStoreProtocol
    let inputChannel: InputChannelProtocol
    let eventStream: EventStreamProtocol
    let csvParser: CSVParserProtocol
    let aiAnalyzer: AIAnalyzerProtocol
    let queryEngine: QueryEngineProtocol
    
    // === 数据导入流程 ===
    
    /// 导入 CSV 文件（完整流程）
    func importCSV(url: URL) async throws -> ImportResult {
        // 1. 解析文件
        let parseResult = try await csvParser.parse(url: url)
        
        // 2. AI 语义分析
        let worldContext = try await metaStore.getWorldModelContext()
        let schemaInfo = SchemaInfo(
            fileName: url.lastPathComponent,
            columns: parseResult.columns,
            rowCount: parseResult.rowCount
        )
        let aiResult = try await aiAnalyzer.analyzeSchema(schemaInfo, context: worldContext)
        
        // 3. 创建草稿对象
        var draftObject = MetaObject(
            id: UUID(),
            name: aiResult.objectSuggestion.name,
            originalName: url.lastPathComponent,
            objectType: .csvFile,
            description: aiResult.objectSuggestion.description,
            filePath: url.path,
            rowCount: parseResult.rowCount,
            properties: [],
            tags: [],
            status: .draft,
            createdAt: Date(),
            updatedAt: Date()
        )
        
        // 4. 创建属性
        let properties = zip(parseResult.columns, aiResult.propertySuggestions).map { (col, suggestion) in
            MetaProperty(
                id: UUID(),
                objectId: draftObject.id,
                originalName: col.name,
                dataType: col.inferredType,
                sampleValues: col.sampleValues,
                nullCount: col.nullCount,
                uniqueCount: col.uniqueCount,
                displayName: suggestion.displayName,
                description: suggestion.description,
                semanticType: suggestion.semanticType,
                unit: suggestion.unit,
                aiInferred: MetaProperty.AIInferredInfo(
                    inferredSemanticType: suggestion.semanticType,
                    confidence: suggestion.confidence,
                    reasoning: suggestion.reasoning,
                    inferredAt: Date()
                )
            )
        }
        draftObject.properties = properties
        
        // 5. 保存草稿
        let savedObject = try await metaStore.createObject(draftObject)
        try await metaStore.saveProperties(properties, objectId: savedObject.id)
        
        // 6. 发送事件
        await eventStream.emit(MetaEvent(
            id: UUID(),
            timestamp: Date(),
            eventType: .objectCreated,
            objectId: savedObject.id,
            actorType: .ai,
            description: "CSV 导入并完成 AI 分析"
        ))
        
        return ImportResult(
            object: savedObject,
            aiAnalysis: aiResult,
            needsConfirmation: true
        )
    }
    
    /// 确认元数据
    func confirmMetadata(objectId: UUID, edits: [MetaEdit]) async throws -> MetaObject {
        var object = try await metaStore.getObject(id: objectId)!
        
        // 应用编辑
        for edit in edits {
            // ... 应用编辑逻辑
        }
        
        object.status = .confirmed
        object.confirmedAt = Date()
        object.updatedAt = Date()
        
        let confirmed = try await metaStore.updateObject(object)
        
        // 发送事件
        await eventStream.emit(MetaEvent(
            id: UUID(),
            timestamp: Date(),
            eventType: .objectConfirmed,
            objectId: objectId,
            actorType: .user,
            description: "用户确认元数据"
        ))
        
        return confirmed
    }
    
    // === 查询分析 ===
    
    /// 自然语言查询
    func query(_ naturalLanguage: String) async throws -> QueryResult {
        let context = try await metaStore.getWorldModelContext()
        return try await queryEngine.executeNL(naturalLanguage, context: context)
    }
    
    /// SQL 查询
    func querySQL(_ sql: String) async throws -> QueryResult {
        return try await queryEngine.executeSQL(sql)
    }
}

struct ImportResult {
    let object: MetaObject
    let aiAnalysis: AIAnalysisResult
    let needsConfirmation: Bool
}
```

## 4. AI Prompt 协议

### 4.1 语义分析 Prompt

```
你是风隐数据语义分析师，负责理解数据的业务含义。

## 任务
分析以下 CSV 数据结构，推断每列的语义类型、业务含义和可能的数据关系。

## 数据信息
文件名: {filename}
总行数: {row_count}

## 列信息
{column_name}:
  - 数据类型: {data_type}
  - 样本值: [{sample_values}]
  - 空值率: {null_rate}%
  - 唯一值数: {unique_count}

## 已有世界模型（可能的关联对象）
{existing_objects_summary}

## 返回 JSON 格式
{
  "object_suggestion": {
    "name": "建议的业务名称",
    "description": "这个数据集描述了什么"
  },
  "properties": [
    {
      "original_name": "原始列名",
      "display_name": "建议的业务名称",
      "semantic_type": "语义类型",
      "description": "业务含义",
      "unit": "单位（如适用）",
      "confidence": 0.85,
      "reasoning": "推断依据"
    }
  ],
  "potential_relations": [
    {
      "source_column": "本表列名",
      "target_object": "目标对象名",
      "target_column": "目标列名",
      "relation_type": "oneToMany",
      "confidence": 0.7,
      "reasoning": "推断依据"
    }
  ],
  "data_quality_notes": ["数据质量观察"]
}
```

### 4.2 NL to SQL Prompt

```
你是风隐数据查询助手，负责将自然语言转换为 SQL。

## 世界模型
{world_model_context}

## 用户查询
{natural_language_query}

## 要求
1. 生成标准 SQL
2. 只使用世界模型中存在的表和字段
3. 使用 display_name 理解用户意图，使用 original_name 生成 SQL

## 返回 JSON 格式
{
  "sql": "SELECT ...",
  "explanation": "这个查询会...",
  "referenced_objects": ["object_id_1", "object_id_2"]
}
```

## 5. 错误码

| 代码 | 说明 |
|------|------|
| `E001` | 文件不存在或无法访问 |
| `E002` | 不支持的文件格式 |
| `E003` | CSV 解析失败 |
| `E004` | AI 分析失败 |
| `E005` | 对象不存在 |
| `E006` | 数据库操作失败 |
| `E007` | 查询执行失败 |
| `E008` | 权限不足 |

## 6. 未来：MCP 集成

星图将通过 MCP (Model Context Protocol) 对外提供服务：

```yaml
# MCP 工具定义草案
tools:
  - name: xingtu_import_csv
    description: 导入 CSV 文件并进行 AI 语义分析
    parameters:
      file_path: string
      
  - name: xingtu_confirm_meta
    description: 确认元数据
    parameters:
      object_id: string
      edits: array
      
  - name: xingtu_query
    description: 自然语言数据查询
    parameters:
      query: string
      
  - name: xingtu_list_objects
    description: 列出所有数据对象
    parameters:
      status: string?
```
