// 星图 (XingTu) - 指标定义模型
// 归属: 星空座 (Xingkongzuo)

import Foundation

/// 星空座：业务指标定义
public struct MetricDef: Identifiable, Codable, Equatable {
    public let id: UUID
    public var name: String                    // 指标代码名
    public var displayName: String             // 显示名称
    public var description: String?            // 业务含义
    public var formula: String                 // 计算公式（SQL 表达式）
    public var sourceObjectIds: [UUID]         // 依赖的数据对象
    public var unit: String?                   // 单位
    public var aggregationType: AggregationType? // 聚合类型
    public var dimensions: [String]            // 可切分维度
    public var tags: [String]
    public var status: MetaObject.Status
    public var createdAt: Date
    public var updatedAt: Date
    
    // MARK: - 聚合类型
    
    public enum AggregationType: String, Codable, CaseIterable {
        case sum = "sum"
        case avg = "avg"
        case count = "count"
        case min = "min"
        case max = "max"
        case countDistinct = "countDistinct"
        
        public var displayName: String {
            switch self {
            case .sum: return "求和"
            case .avg: return "平均值"
            case .count: return "计数"
            case .min: return "最小值"
            case .max: return "最大值"
            case .countDistinct: return "去重计数"
            }
        }
        
        public var sqlFunction: String {
            switch self {
            case .sum: return "SUM"
            case .avg: return "AVG"
            case .count: return "COUNT"
            case .min: return "MIN"
            case .max: return "MAX"
            case .countDistinct: return "COUNT(DISTINCT"
            }
        }
    }
    
    // MARK: - 初始化
    
    public init(
        id: UUID = UUID(),
        name: String,
        displayName: String,
        description: String? = nil,
        formula: String,
        sourceObjectIds: [UUID] = [],
        unit: String? = nil,
        aggregationType: AggregationType? = nil,
        dimensions: [String] = [],
        tags: [String] = [],
        status: MetaObject.Status = .draft,
        createdAt: Date = Date(),
        updatedAt: Date = Date()
    ) {
        self.id = id
        self.name = name
        self.displayName = displayName
        self.description = description
        self.formula = formula
        self.sourceObjectIds = sourceObjectIds
        self.unit = unit
        self.aggregationType = aggregationType
        self.dimensions = dimensions
        self.tags = tags
        self.status = status
        self.createdAt = createdAt
        self.updatedAt = updatedAt
    }
    
    // MARK: - 便捷方法
    
    /// 生成完整 SQL
    public func generateSQL(groupBy: [String]? = nil) -> String {
        var sql = "SELECT \(formula) AS \(name)"
        
        if let dims = groupBy, !dims.isEmpty {
            sql = "SELECT \(dims.joined(separator: ", ")), \(formula) AS \(name)"
            sql += " GROUP BY \(dims.joined(separator: ", "))"
        }
        
        return sql
    }
}

// MARK: - 摘要

extension MetricDef {
    /// 生成指标摘要
    public var summary: MetricDefSummary {
        MetricDefSummary(
            id: id,
            name: name,
            displayName: displayName,
            description: description,
            unit: unit
        )
    }
}

/// 指标定义摘要
public struct MetricDefSummary: Codable {
    public let id: UUID
    public let name: String
    public let displayName: String
    public let description: String?
    public let unit: String?
}
