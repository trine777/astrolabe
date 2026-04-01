// 星图 (XingTu) - 元数据属性模型
// 归属: 星空座 (Xingkongzuo)

import Foundation

/// 星空座：对象的一个"属性"（字段、列）
public struct MetaProperty: Identifiable, Codable, Equatable {
    public let id: UUID
    public let objectId: UUID                  // 所属对象
    
    // MARK: - 原始信息（从数据解析）
    
    public var originalName: String            // 原始列名
    public var dataType: DataType              // 物理数据类型
    public var sampleValues: [String]          // 样本值
    public var nullCount: Int                  // 空值数量
    public var uniqueCount: Int                // 唯一值数量
    
    // MARK: - 用户定义的语义层（星空座核心）
    
    public var displayName: String             // 业务名称（用户定义）
    public var description: String?            // 业务含义
    public var semanticType: SemanticType?     // 语义类型
    public var unit: String?                   // 单位（如：元、%、人）
    public var format: String?                 // 显示格式
    public var businessRules: String?          // 业务规则说明
    
    // MARK: - 可视化偏好
    
    public var visualPreference: VisualPreference?
    
    // MARK: - 确认状态

    /// 用户确认时间（非 nil 表示用户已审核，无论是否修改了 AI 建议）
    public var userConfirmedAt: Date?

    // MARK: - AI 推断信息

    public var aiInferred: AIInferredInfo?
    
    // MARK: - 数据类型
    
    public enum DataType: String, Codable, CaseIterable {
        case string = "string"
        case integer = "integer"
        case decimal = "decimal"
        case boolean = "boolean"
        case date = "date"
        case datetime = "datetime"
        case json = "json"
        case unknown = "unknown"
        
        public var displayName: String {
            switch self {
            case .string: return "字符串"
            case .integer: return "整数"
            case .decimal: return "小数"
            case .boolean: return "布尔"
            case .date: return "日期"
            case .datetime: return "日期时间"
            case .json: return "JSON"
            case .unknown: return "未知"
            }
        }
        
        public var icon: String {
            switch self {
            case .string: return "textformat"
            case .integer: return "number"
            case .decimal: return "number.circle"
            case .boolean: return "checkmark.circle"
            case .date: return "calendar"
            case .datetime: return "clock"
            case .json: return "curlybraces"
            case .unknown: return "questionmark"
            }
        }
    }
    
    // MARK: - 语义类型
    
    public enum SemanticType: String, Codable, CaseIterable {
        // 标识类
        case primaryKey = "primaryKey"
        case foreignKey = "foreignKey"
        case uniqueId = "uniqueId"
        
        // 实体类
        case personName = "personName"
        case orgName = "orgName"
        case productName = "productName"
        case placeName = "placeName"
        
        // 联系类
        case email = "email"
        case phone = "phone"
        case address = "address"
        case url = "url"
        
        // 度量类
        case amount = "amount"
        case quantity = "quantity"
        case percentage = "percentage"
        case ratio = "ratio"
        case score = "score"
        
        // 时间类
        case timestamp = "timestamp"
        case dateOnly = "dateOnly"
        case timeOnly = "timeOnly"
        case duration = "duration"
        
        // 分类类
        case category = "category"
        case status = "status"
        case tag = "tag"
        case code = "code"
        
        // 其他
        case freeText = "freeText"
        case unknown = "unknown"
        
        public var displayName: String {
            switch self {
            case .primaryKey: return "主键"
            case .foreignKey: return "外键"
            case .uniqueId: return "唯一标识"
            case .personName: return "人名"
            case .orgName: return "组织名"
            case .productName: return "产品名"
            case .placeName: return "地点名"
            case .email: return "邮箱"
            case .phone: return "电话"
            case .address: return "地址"
            case .url: return "网址"
            case .amount: return "金额"
            case .quantity: return "数量"
            case .percentage: return "百分比"
            case .ratio: return "比率"
            case .score: return "评分"
            case .timestamp: return "时间戳"
            case .dateOnly: return "日期"
            case .timeOnly: return "时间"
            case .duration: return "时长"
            case .category: return "分类"
            case .status: return "状态"
            case .tag: return "标签"
            case .code: return "代码"
            case .freeText: return "自由文本"
            case .unknown: return "未知"
            }
        }
        
        public var category: String {
            switch self {
            case .primaryKey, .foreignKey, .uniqueId:
                return "标识类"
            case .personName, .orgName, .productName, .placeName:
                return "实体类"
            case .email, .phone, .address, .url:
                return "联系类"
            case .amount, .quantity, .percentage, .ratio, .score:
                return "度量类"
            case .timestamp, .dateOnly, .timeOnly, .duration:
                return "时间类"
            case .category, .status, .tag, .code:
                return "分类类"
            case .freeText, .unknown:
                return "其他"
            }
        }
    }
    
    // MARK: - 可视化偏好
    
    public struct VisualPreference: Codable, Equatable {
        public var chartType: String?          // 推荐图表类型
        public var colorScheme: String?        // 配色方案
        public var aggregation: String?        // 默认聚合方式
        
        public init(
            chartType: String? = nil,
            colorScheme: String? = nil,
            aggregation: String? = nil
        ) {
            self.chartType = chartType
            self.colorScheme = colorScheme
            self.aggregation = aggregation
        }
    }
    
    // MARK: - AI 推断信息
    
    public struct AIInferredInfo: Codable, Equatable {
        public var inferredSemanticType: SemanticType?
        public var confidence: Double          // 置信度 0-1
        public var reasoning: String?          // AI 推理说明
        public var inferredAt: Date
        
        public init(
            inferredSemanticType: SemanticType?,
            confidence: Double,
            reasoning: String? = nil,
            inferredAt: Date = Date()
        ) {
            self.inferredSemanticType = inferredSemanticType
            self.confidence = confidence
            self.reasoning = reasoning
            self.inferredAt = inferredAt
        }
    }
    
    // MARK: - 初始化
    
    public init(
        id: UUID = UUID(),
        objectId: UUID,
        originalName: String,
        dataType: DataType,
        sampleValues: [String] = [],
        nullCount: Int = 0,
        uniqueCount: Int = 0,
        displayName: String? = nil,
        description: String? = nil,
        semanticType: SemanticType? = nil,
        unit: String? = nil,
        format: String? = nil,
        businessRules: String? = nil,
        visualPreference: VisualPreference? = nil,
        userConfirmedAt: Date? = nil,
        aiInferred: AIInferredInfo? = nil
    ) {
        self.id = id
        self.objectId = objectId
        self.originalName = originalName
        self.dataType = dataType
        self.sampleValues = sampleValues
        self.nullCount = nullCount
        self.uniqueCount = uniqueCount
        self.displayName = displayName ?? originalName
        self.description = description
        self.semanticType = semanticType
        self.unit = unit
        self.format = format
        self.businessRules = businessRules
        self.visualPreference = visualPreference
        self.userConfirmedAt = userConfirmedAt
        self.aiInferred = aiInferred
    }
    
    // MARK: - 便捷方法
    
    /// 空值率
    public func nullRate(totalRows: Int) -> Double {
        guard totalRows > 0 else { return 0 }
        return Double(nullCount) / Double(totalRows)
    }
    
    /// 是否已被用户确认
    /// true = 用户已审核过此属性（无论是否修改了 AI 建议）
    public var isUserConfirmed: Bool {
        return userConfirmedAt != nil
    }
}

// MARK: - 摘要

extension MetaProperty {
    /// 生成属性摘要（用于 AI 上下文）
    public var summary: MetaPropertySummary {
        MetaPropertySummary(
            id: id,
            originalName: originalName,
            displayName: displayName,
            dataType: dataType.rawValue,
            semanticType: semanticType?.rawValue,
            description: description
        )
    }
}

/// 元数据属性摘要
public struct MetaPropertySummary: Codable {
    public let id: UUID
    public let originalName: String
    public let displayName: String
    public let dataType: String
    public let semanticType: String?
    public let description: String?
}
