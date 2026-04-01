// 星图 (XingTu) - AI 服务
// 接入 OpenAI API 进行语义分析

import Foundation

/// AI 服务协议
public protocol AIServiceProtocol {
    /// 分析用户请求并生成操作
    func analyzeRequest(
        userInput: String,
        context: AIContext
    ) async throws -> AIAnalysisResult
    
    /// 推断字段语义类型
    func inferSemanticTypes(
        properties: [PropertyInfo],
        objectName: String
    ) async throws -> [SemanticInference]
}

/// AI 上下文
public struct AIContext: Codable {
    public let objectName: String
    public let objectDescription: String?
    public let properties: [PropertyInfo]
    
    public init(objectName: String, objectDescription: String?, properties: [PropertyInfo]) {
        self.objectName = objectName
        self.objectDescription = objectDescription
        self.properties = properties
    }
}

/// 属性信息（用于 AI 分析）
public struct PropertyInfo: Codable {
    public let id: String
    public let originalName: String
    public let displayName: String
    public let dataType: String
    public let semanticType: String?
    public let sampleValues: [String]
    public let nullCount: Int
    public let uniqueCount: Int
    
    public init(from property: MetaProperty) {
        self.id = property.id.uuidString
        self.originalName = property.originalName
        self.displayName = property.displayName
        self.dataType = property.dataType.rawValue
        self.semanticType = property.semanticType?.rawValue
        self.sampleValues = Array(property.sampleValues.prefix(5))
        self.nullCount = property.nullCount
        self.uniqueCount = property.uniqueCount
    }
}

/// AI 分析结果
public struct AIAnalysisResult: Codable {
    public let message: String
    public let actions: [AIActionResult]
    public let confidence: Double
    
    public init(message: String, actions: [AIActionResult], confidence: Double = 1.0) {
        self.message = message
        self.actions = actions
        self.confidence = confidence
    }
}

/// AI 操作结果
public struct AIActionResult: Codable {
    public let type: ActionType
    public let propertyId: String
    public let value: String
    
    public enum ActionType: String, Codable {
        case rename
        case setSemanticType
        case setDescription
        case setUnit
    }
    
    public init(type: ActionType, propertyId: String, value: String) {
        self.type = type
        self.propertyId = propertyId
        self.value = value
    }
}

/// 语义推断结果
public struct SemanticInference: Codable {
    public let propertyId: String
    public let originalName: String      // 原始列名
    public let inferredType: String      // 推断的语义类型
    public let semanticType: String      // 语义类型（别名）
    public let displayName: String?      // 推断的显示名称
    public let description: String?      // 推断的描述
    public let confidence: Double
    public let reasoning: String
    
    public init(
        propertyId: String,
        originalName: String,
        inferredType: String,
        displayName: String? = nil,
        description: String? = nil,
        confidence: Double,
        reasoning: String
    ) {
        self.propertyId = propertyId
        self.originalName = originalName
        self.inferredType = inferredType
        self.semanticType = inferredType
        self.displayName = displayName
        self.description = description
        self.confidence = confidence
        self.reasoning = reasoning
    }
}

/// AI 服务提供商
public enum AIProvider: String, CaseIterable {
    case openai = "OpenAI"
    case qwen = "通义千问"
    case custom = "自定义"
    
    public var defaultBaseURL: String {
        switch self {
        case .openai: return "https://api.openai.com/v1"
        case .qwen: return "https://dashscope.aliyuncs.com/compatible-mode/v1"
        case .custom: return ""
        }
    }
    
    public var defaultModel: String {
        switch self {
        case .openai: return "gpt-4o-mini"
        case .qwen: return "qwen-plus"
        case .custom: return ""
        }
    }
    
    public var envKeyName: String {
        switch self {
        case .openai: return "OPENAI_API_KEY"
        case .qwen: return "DASHSCOPE_API_KEY"
        case .custom: return "AI_API_KEY"
        }
    }
}

/// OpenAI 兼容服务实现（支持 OpenAI、通义千问等）
public class OpenAIService: AIServiceProtocol {
    
    private let apiKey: String
    private let model: String
    private let baseURL: String
    public let provider: AIProvider
    
    public init(
        apiKey: String,
        model: String = "gpt-4o-mini",
        baseURL: String = "https://api.openai.com/v1",
        provider: AIProvider = .openai
    ) {
        self.apiKey = apiKey
        self.model = model
        self.baseURL = baseURL
        self.provider = provider
    }
    
    /// 创建通义千问服务
    public static func qwen(apiKey: String, model: String = "qwen-plus") -> OpenAIService {
        return OpenAIService(
            apiKey: apiKey,
            model: model,
            baseURL: "https://dashscope.aliyuncs.com/compatible-mode/v1",
            provider: .qwen
        )
    }
    
    /// 从环境变量创建（优先检测通义千问）
    public static func fromEnvironment() -> OpenAIService? {
        // 优先检测通义千问
        if let qwenKey = ProcessInfo.processInfo.environment["DASHSCOPE_API_KEY"] {
            let model = ProcessInfo.processInfo.environment["QWEN_MODEL"] ?? "qwen-plus"
            return OpenAIService.qwen(apiKey: qwenKey, model: model)
        }
        
        // 检测 OpenAI
        if let openaiKey = ProcessInfo.processInfo.environment["OPENAI_API_KEY"] {
            let baseURL = ProcessInfo.processInfo.environment["OPENAI_BASE_URL"] ?? "https://api.openai.com/v1"
            let model = ProcessInfo.processInfo.environment["OPENAI_MODEL"] ?? "gpt-4o-mini"
            return OpenAIService(apiKey: openaiKey, model: model, baseURL: baseURL, provider: .openai)
        }
        
        // 检测通用 AI 配置
        if let apiKey = ProcessInfo.processInfo.environment["AI_API_KEY"],
           let baseURL = ProcessInfo.processInfo.environment["AI_BASE_URL"] {
            let model = ProcessInfo.processInfo.environment["AI_MODEL"] ?? "gpt-4o-mini"
            return OpenAIService(apiKey: apiKey, model: model, baseURL: baseURL, provider: .custom)
        }
        
        return nil
    }
    
    // MARK: - 分析用户请求
    
    public func analyzeRequest(
        userInput: String,
        context: AIContext
    ) async throws -> AIAnalysisResult {
        let systemPrompt = buildSystemPrompt(context: context)
        let userPrompt = buildUserPrompt(userInput: userInput, context: context)
        
        let response = try await callOpenAI(
            systemPrompt: systemPrompt,
            userPrompt: userPrompt
        )
        
        return try parseAnalysisResponse(response)
    }
    
    // MARK: - 推断语义类型
    
    public func inferSemanticTypes(
        properties: [PropertyInfo],
        objectName: String
    ) async throws -> [SemanticInference] {
        let systemPrompt = """
        你是一个数据分析专家，负责分析数据字段的语义类型。
        
        可用的语义类型：
        - primaryKey: 主键
        - foreignKey: 外键
        - uniqueId: 唯一标识
        - personName: 人名
        - orgName: 组织名
        - productName: 产品名
        - email: 邮箱
        - phone: 电话
        - address: 地址
        - amount: 金额
        - quantity: 数量
        - percentage: 百分比
        - timestamp: 时间戳
        - dateOnly: 日期
        - category: 分类
        - status: 状态
        - freeText: 自由文本
        
        请分析每个字段，返回 JSON 格式：
        {
            "inferences": [
                {
                    "propertyId": "字段ID",
                    "inferredType": "语义类型",
                    "confidence": 0.95,
                    "reasoning": "推理说明"
                }
            ]
        }
        """
        
        let propertiesJson = try JSONEncoder().encode(properties)
        let propertiesStr = String(data: propertiesJson, encoding: .utf8) ?? "[]"
        
        let userPrompt = """
        数据源名称：\(objectName)
        
        字段信息：
        \(propertiesStr)
        
        请分析每个字段的语义类型。
        """
        
        let response = try await callOpenAI(
            systemPrompt: systemPrompt,
            userPrompt: userPrompt
        )
        
        return try parseInferenceResponse(response)
    }
    
    // MARK: - 私有方法
    
    private func buildSystemPrompt(context: AIContext) -> String {
        let propertiesList = context.properties.map { prop in
            "- \(prop.originalName) (业务名: \(prop.displayName), 类型: \(prop.dataType), 样本: \(prop.sampleValues.joined(separator: ", ")))"
        }.joined(separator: "\n")
        
        return """
        你是星图元数据助手，帮助用户管理数据源的元数据。
        
        当前数据源：\(context.objectName)
        \(context.objectDescription.map { "描述：\($0)" } ?? "")
        
        字段列表：
        \(propertiesList)
        
        你可以执行以下操作：
        1. rename - 重命名字段的业务名称
        2. setSemanticType - 设置字段的语义类型
        3. setDescription - 设置字段的业务描述
        4. setUnit - 设置字段的单位
        
        可用的语义类型：primaryKey, foreignKey, uniqueId, personName, orgName, productName, email, phone, address, amount, quantity, percentage, timestamp, dateOnly, category, status, freeText
        
        请根据用户的请求，返回 JSON 格式的响应：
        {
            "message": "给用户的回复消息",
            "actions": [
                {
                    "type": "rename",
                    "propertyId": "字段ID",
                    "value": "新名称"
                }
            ],
            "confidence": 0.95
        }
        
        如果用户的请求不清楚，返回一个友好的提示消息，actions 为空数组。
        """
    }
    
    private func buildUserPrompt(userInput: String, context: AIContext) -> String {
        return userInput
    }
    
    private func callOpenAI(systemPrompt: String, userPrompt: String) async throws -> String {
        let url = URL(string: "\(baseURL)/chat/completions")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        
        let body: [String: Any] = [
            "model": model,
            "messages": [
                ["role": "system", "content": systemPrompt],
                ["role": "user", "content": userPrompt]
            ],
            "temperature": 0.3,
            "response_format": ["type": "json_object"]
        ]
        
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw AIServiceError.invalidResponse
        }
        
        guard httpResponse.statusCode == 200 else {
            let errorMessage = String(data: data, encoding: .utf8) ?? "Unknown error"
            throw AIServiceError.apiError(statusCode: httpResponse.statusCode, message: errorMessage)
        }
        
        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let choices = json["choices"] as? [[String: Any]],
              let firstChoice = choices.first,
              let message = firstChoice["message"] as? [String: Any],
              let content = message["content"] as? String else {
            throw AIServiceError.parseError("Failed to parse OpenAI response")
        }
        
        return content
    }
    
    private func parseAnalysisResponse(_ response: String) throws -> AIAnalysisResult {
        guard let data = response.data(using: .utf8) else {
            throw AIServiceError.parseError("Invalid response encoding")
        }
        
        return try JSONDecoder().decode(AIAnalysisResult.self, from: data)
    }
    
    private func parseInferenceResponse(_ response: String) throws -> [SemanticInference] {
        guard let data = response.data(using: .utf8) else {
            throw AIServiceError.parseError("Invalid response encoding")
        }
        
        struct InferenceResponse: Codable {
            let inferences: [SemanticInference]
        }
        
        let result = try JSONDecoder().decode(InferenceResponse.self, from: data)
        return result.inferences
    }
}

/// AI 服务错误
public enum AIServiceError: Error, LocalizedError {
    case noAPIKey
    case invalidResponse
    case apiError(statusCode: Int, message: String)
    case parseError(String)
    
    public var errorDescription: String? {
        switch self {
        case .noAPIKey:
            return "未配置 OpenAI API Key"
        case .invalidResponse:
            return "无效的 API 响应"
        case .apiError(let code, let message):
            return "API 错误 (\(code)): \(message)"
        case .parseError(let message):
            return "解析错误: \(message)"
        }
    }
}
