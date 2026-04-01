// 星图 (XingTu) - 元数据对象模型
// 归属: 星空座 (Xingkongzuo)

import Foundation

/// 星空座：数据世界中的一个"实体"（表、CSV、视图等）
public struct MetaObject: Identifiable, Codable, Equatable {
    public let id: UUID
    public var name: String                    // 业务名称（用户定义）
    public var originalName: String            // 原始名称（文件名/表名）
    public var objectType: ObjectType          // 对象类型
    public var description: String?            // 业务含义描述
    public var filePath: String?               // 原始文件路径
    public var rowCount: Int?                  // 数据行数
    public var tags: [String]                  // 标签体系
    public var status: Status                  // 状态
    public var createdAt: Date
    public var updatedAt: Date
    public var confirmedAt: Date?              // 用户确认时间
    public var confirmedBy: String?            // 确认人
    
    // MARK: - 对象类型
    
    public enum ObjectType: String, Codable, CaseIterable {
        case csvFile = "csvFile"       // CSV 文件
        case table = "table"           // 数据库表
        case view = "view"             // 视图
        case derived = "derived"       // 派生数据集
        case external = "external"     // 外部数据源
        
        public var displayName: String {
            switch self {
            case .csvFile: return "CSV 文件"
            case .table: return "数据库表"
            case .view: return "视图"
            case .derived: return "派生数据集"
            case .external: return "外部数据源"
            }
        }
        
        public var icon: String {
            switch self {
            case .csvFile: return "doc.text"
            case .table: return "tablecells"
            case .view: return "eye"
            case .derived: return "arrow.triangle.branch"
            case .external: return "link"
            }
        }
    }
    
    // MARK: - 状态
    
    public enum Status: String, Codable, CaseIterable {
        case draft = "draft"           // 草稿（AI 推断，待确认）
        case confirmed = "confirmed"   // 已确认（用户校验）
        case published = "published"   // 已发布（可供分析）
        case archived = "archived"     // 已归档
        
        public var displayName: String {
            switch self {
            case .draft: return "草稿"
            case .confirmed: return "已确认"
            case .published: return "已发布"
            case .archived: return "已归档"
            }
        }
        
        public var color: String {
            switch self {
            case .draft: return "orange"
            case .confirmed: return "blue"
            case .published: return "green"
            case .archived: return "gray"
            }
        }
    }
    
    // MARK: - 初始化
    
    public init(
        id: UUID = UUID(),
        name: String,
        originalName: String,
        objectType: ObjectType,
        description: String? = nil,
        filePath: String? = nil,
        rowCount: Int? = nil,
        tags: [String] = [],
        status: Status = .draft,
        createdAt: Date = Date(),
        updatedAt: Date = Date(),
        confirmedAt: Date? = nil,
        confirmedBy: String? = nil
    ) {
        self.id = id
        self.name = name
        self.originalName = originalName
        self.objectType = objectType
        self.description = description
        self.filePath = filePath
        self.rowCount = rowCount
        self.tags = tags
        self.status = status
        self.createdAt = createdAt
        self.updatedAt = updatedAt
        self.confirmedAt = confirmedAt
        self.confirmedBy = confirmedBy
    }
    
    // MARK: - 便捷方法
    
    /// 从 CSV 文件创建草稿对象
    public static func fromCSV(
        url: URL,
        suggestedName: String? = nil,
        rowCount: Int? = nil
    ) -> MetaObject {
        let fileName = url.deletingPathExtension().lastPathComponent
        return MetaObject(
            name: suggestedName ?? fileName,
            originalName: url.lastPathComponent,
            objectType: .csvFile,
            filePath: url.path,
            rowCount: rowCount,
            status: .draft
        )
    }
    
    /// 确认对象
    public mutating func confirm(by user: String? = nil) {
        self.status = .confirmed
        self.confirmedAt = Date()
        self.confirmedBy = user
        self.updatedAt = Date()
    }
    
    /// 发布对象
    public mutating func publish() {
        self.status = .published
        self.updatedAt = Date()
    }
    
    /// 归档对象
    public mutating func archive() {
        self.status = .archived
        self.updatedAt = Date()
    }
}

// MARK: - 摘要（供 AI 使用）

extension MetaObject {
    /// 生成对象摘要（用于 AI 上下文）
    public var summary: MetaObjectSummary {
        MetaObjectSummary(
            id: id,
            name: name,
            objectType: objectType.rawValue,
            description: description,
            rowCount: rowCount,
            status: status.rawValue
        )
    }
}

/// 元数据对象摘要（轻量级，用于 AI 上下文）
public struct MetaObjectSummary: Codable {
    public let id: UUID
    public let name: String
    public let objectType: String
    public let description: String?
    public let rowCount: Int?
    public let status: String
}
