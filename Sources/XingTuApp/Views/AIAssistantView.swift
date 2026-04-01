// 星图 - AI 对话助手视图
// 支持自然语言修改元数据

import SwiftUI
import XingTu

struct AIAssistantView: View {
    @EnvironmentObject var appState: AppState
    let object: MetaObject
    @Binding var properties: [MetaProperty]
    
    @State private var inputText = ""
    @State private var messages: [ChatMessage] = []
    @State private var isProcessing = false
    @State private var aiService: OpenAIService?
    @State private var showAPIConfig = false
    @State private var selectedProvider: AIProvider = .qwen
    @State private var apiKeyInput = ""
    @State private var baseURLInput = ""
    @State private var modelInput = ""
    
    var body: some View {
        VStack(spacing: 0) {
            // 头部
            HStack {
                Image(systemName: "sparkles")
                    .foregroundColor(.xingtuAccent)
                
                Text("AI 元数据助手")
                    .font(.headline)
                
                // API 状态指示
                if let service = aiService {
                    HStack(spacing: 4) {
                        Circle()
                            .fill(Color.green)
                            .frame(width: 8, height: 8)
                        Text(service.provider.rawValue)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    .help("已连接 \(service.provider.rawValue)")
                } else {
                    Button(action: { showAPIConfig = true }) {
                        Label("配置 API", systemImage: "key")
                            .font(.caption)
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                }
                
                Spacer()
                
                if aiService != nil {
                    Button(action: { showAPIConfig = true }) {
                        Image(systemName: "gearshape")
                    }
                    .buttonStyle(.plain)
                    .foregroundColor(.secondary)
                }
                
                Button(action: clearMessages) {
                    Image(systemName: "trash")
                }
                .buttonStyle(.plain)
                .foregroundColor(.secondary)
            }
            .padding()
            .background(Color.xingtuSecondaryBackground)
            .onAppear {
                loadAIServiceFromSettings()
            }
            .sheet(isPresented: $showAPIConfig) {
                APIConfigSheet(
                    selectedProvider: $selectedProvider,
                    apiKeyInput: $apiKeyInput,
                    baseURLInput: $baseURLInput,
                    modelInput: $modelInput,
                    onSave: saveAPIConfig,
                    onCancel: { showAPIConfig = false }
                )
            }
            
            Divider()
            
            // 消息列表
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 12) {
                        // 欢迎消息
                        if messages.isEmpty {
                            WelcomeMessage(objectName: object.name, propertyCount: properties.count)
                        }
                        
                        ForEach(messages) { message in
                            MessageBubble(message: message)
                                .id(message.id)
                        }
                        
                        if isProcessing {
                            HStack {
                                ProgressView()
                                    .scaleEffect(0.8)
                                Text("思考中...")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                            .padding()
                        }
                    }
                    .padding()
                }
                .onChange(of: messages.count) { _, _ in
                    if let lastMessage = messages.last {
                        withAnimation {
                            proxy.scrollTo(lastMessage.id, anchor: .bottom)
                        }
                    }
                }
            }
            
            Divider()
            
            // 输入区域
            HStack(alignment: .bottom, spacing: 12) {
                ZStack(alignment: .topLeading) {
                    // 占位符
                    if inputText.isEmpty {
                        Text("描述修改，如：把 完整版 改名为「公司名称」")
                            .foregroundColor(.secondary.opacity(0.6))
                            .padding(.horizontal, 8)
                            .padding(.vertical, 10)
                            .allowsHitTesting(false)
                    }
                    
                    // 输入框
                    TextEditor(text: $inputText)
                        .font(.body)
                        .scrollContentBackground(.hidden)
                        .background(Color.clear)
                        .frame(minHeight: 36, maxHeight: 80)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .padding(4)
                .background(Color.xingtuBackground)
                .cornerRadius(8)
                .overlay(
                    RoundedRectangle(cornerRadius: 8)
                        .stroke(Color.xingtuAccent.opacity(0.5), lineWidth: 1)
                )
                
                Button(action: sendMessage) {
                    Image(systemName: "arrow.up.circle.fill")
                        .font(.title2)
                        .foregroundColor(inputText.isEmpty ? .secondary : .xingtuAccent)
                }
                .buttonStyle(.plain)
                .disabled(inputText.isEmpty || isProcessing)
                .keyboardShortcut(.return, modifiers: .command)
            }
            .padding()
            .background(Color.xingtuSecondaryBackground)
        }
        .frame(width: 400)
    }
    
    private func sendMessage() {
        let userInput = inputText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !userInput.isEmpty else { return }
        
        // 添加用户消息
        let userMessage = ChatMessage(role: .user, content: userInput)
        messages.append(userMessage)
        inputText = ""
        
        // 处理请求
        isProcessing = true
        
        Task {
            let response = await processUserRequest(userInput)
            
            let assistantMessage = ChatMessage(role: .assistant, content: response.message, actions: response.actions)
            messages.append(assistantMessage)
            
            // 执行动作
            for action in response.actions {
                await executeAction(action)
            }
            
            isProcessing = false
        }
    }
    
    private func processUserRequest(_ input: String) async -> AIResponse {
        // 如果有 AI 服务，使用 API
        if let service = aiService {
            do {
                let context = AIContext(
                    objectName: object.name,
                    objectDescription: object.description,
                    properties: properties.map { PropertyInfo(from: $0) }
                )
                
                let result = try await service.analyzeRequest(
                    userInput: input,
                    context: context
                )
                
                // 转换 API 结果为本地格式
                let actions = result.actions.compactMap { action -> AIAction? in
                    guard let propertyId = UUID(uuidString: action.propertyId) else { return nil }
                    
                    switch action.type {
                    case .rename:
                        return .rename(propertyId: propertyId, newName: action.value)
                    case .setSemanticType:
                        if let type = MetaProperty.SemanticType(rawValue: action.value) {
                            return .setSemanticType(propertyId: propertyId, type: type)
                        }
                        return nil
                    case .setDescription:
                        return .setDescription(propertyId: propertyId, description: action.value)
                    case .setUnit:
                        return .setUnit(propertyId: propertyId, unit: action.value)
                    }
                }
                
                return AIResponse(message: result.message, actions: actions)
            } catch {
                return AIResponse(
                    message: "AI 服务出错：\(error.localizedDescription)\n\n回退到本地解析...",
                    actions: []
                )
            }
        }
        
        // 本地解析（备用）
        return localParseRequest(input)
    }
    
    private func localParseRequest(_ input: String) -> AIResponse {
        let lowercased = input.lowercased()
        
        // 重命名字段
        if lowercased.contains("改名") || lowercased.contains("重命名") || lowercased.contains("rename") {
            return parseRenameIntent(input)
        }
        
        // 设置语义类型
        if lowercased.contains("类型") || lowercased.contains("设为") || lowercased.contains("标记为") {
            return parseSemanticTypeIntent(input)
        }
        
        // 添加描述
        if lowercased.contains("描述") || lowercased.contains("说明") || lowercased.contains("解释") {
            return parseDescriptionIntent(input)
        }
        
        // 批量操作
        if lowercased.contains("所有") || lowercased.contains("全部") {
            return parseBatchIntent(input)
        }
        
        // 默认回复
        return AIResponse(
            message: """
            我可以帮你修改元数据，试试这些指令：
            
            • **重命名**: "把 col1 改名为「用户姓名」"
            • **设置类型**: "把 amount 标记为金额类型"
            • **添加描述**: "给 user_id 添加描述：用户唯一标识"
            • **批量操作**: "把所有空值多的字段标记为可选"
            
            你也可以用自然语言描述需求。
            """,
            actions: []
        )
    }
    
    private func parseRenameIntent(_ input: String) -> AIResponse {
        // 解析重命名意图
        // 示例: "把 col1 改名为 用户姓名"
        
        for prop in properties {
            if input.contains(prop.originalName) || input.contains(prop.displayName) {
                // 尝试提取新名称
                let patterns = ["改名为", "重命名为", "改成", "叫做", "改为"]
                for pattern in patterns {
                    if let range = input.range(of: pattern) {
                        var newName = String(input[range.upperBound...])
                            .trimmingCharacters(in: .whitespaces)
                            .replacingOccurrences(of: "「", with: "")
                            .replacingOccurrences(of: "」", with: "")
                            .replacingOccurrences(of: "\"", with: "")
                        
                        // 截取到标点或空格
                        if let endIndex = newName.firstIndex(where: { $0.isPunctuation && $0 != "_" }) {
                            newName = String(newName[..<endIndex])
                        }
                        
                        if !newName.isEmpty {
                            return AIResponse(
                                message: "好的，我将把 **\(prop.originalName)** 的业务名称从「\(prop.displayName)」改为「\(newName)」",
                                actions: [.rename(propertyId: prop.id, newName: newName)]
                            )
                        }
                    }
                }
            }
        }
        
        return AIResponse(
            message: "抱歉，我没有找到要重命名的字段。请指定字段名称，例如：「把 user_name 改名为 用户姓名」",
            actions: []
        )
    }
    
    private func parseSemanticTypeIntent(_ input: String) -> AIResponse {
        // 解析语义类型设置意图
        
        let typeMapping: [(keywords: [String], type: MetaProperty.SemanticType)] = [
            (["金额", "钱", "价格", "费用"], .amount),
            (["数量", "个数", "数目"], .quantity),
            (["百分比", "比例", "%"], .percentage),
            (["邮箱", "email", "邮件"], .email),
            (["电话", "手机", "phone"], .phone),
            (["地址", "address"], .address),
            (["日期", "时间", "date", "time"], .timestamp),
            (["主键", "id", "标识"], .primaryKey),
            (["姓名", "名字", "人名"], .personName),
            (["状态", "status"], .status),
            (["分类", "类别", "category"], .category)
        ]
        
        for prop in properties {
            if input.contains(prop.originalName) || input.contains(prop.displayName) {
                for (keywords, type) in typeMapping {
                    if keywords.contains(where: { input.contains($0) }) {
                        return AIResponse(
                            message: "好的，我将把 **\(prop.originalName)** 的语义类型设置为「\(type.displayName)」",
                            actions: [.setSemanticType(propertyId: prop.id, type: type)]
                        )
                    }
                }
            }
        }
        
        return AIResponse(
            message: "请指定要设置的字段和类型，例如：「把 price 标记为金额类型」",
            actions: []
        )
    }
    
    private func parseDescriptionIntent(_ input: String) -> AIResponse {
        // 解析描述设置意图
        
        for prop in properties {
            if input.contains(prop.originalName) || input.contains(prop.displayName) {
                let patterns = ["描述", "说明", "解释"]
                for pattern in patterns {
                    if let range = input.range(of: pattern + "：") ?? input.range(of: pattern + ":") {
                        let description = String(input[range.upperBound...]).trimmingCharacters(in: .whitespaces)
                        if !description.isEmpty {
                            return AIResponse(
                                message: "好的，我将为 **\(prop.originalName)** 添加描述",
                                actions: [.setDescription(propertyId: prop.id, description: description)]
                            )
                        }
                    }
                }
            }
        }
        
        return AIResponse(
            message: "请指定字段和描述内容，例如：「给 user_id 添加描述：用户唯一标识符」",
            actions: []
        )
    }
    
    private func parseBatchIntent(_ input: String) -> AIResponse {
        // 批量操作（简化实现）
        return AIResponse(
            message: "批量操作功能正在开发中，目前支持单个字段的修改。",
            actions: []
        )
    }
    
    private func executeAction(_ action: AIAction) async {
        guard let index = properties.firstIndex(where: { $0.id == action.propertyId }) else { return }
        
        var updated = properties[index]
        let oldValue: String
        let newValue: String
        
        switch action {
        case .rename(_, let newName):
            oldValue = updated.displayName
            updated.displayName = newName
            newValue = newName
            
        case .setSemanticType(_, let type):
            oldValue = updated.semanticType?.displayName ?? "-"
            updated.semanticType = type
            newValue = type.displayName
            
        case .setDescription(_, let description):
            oldValue = updated.description ?? "-"
            updated.description = description
            newValue = description
            
        case .setUnit(_, let unit):
            oldValue = updated.unit ?? "-"
            updated.unit = unit
            newValue = unit
        }
        
        do {
            _ = try await appState.service.metaStore.updateProperty(updated)
            
            await appState.service.eventStream.emitPropertyUpdated(
                objectId: object.id,
                propertyId: updated.id,
                by: .ai,
                before: oldValue,
                after: newValue
            )
            
            properties[index] = updated
        } catch {
            appState.errorMessage = error.localizedDescription
        }
    }
    
    private func clearMessages() {
        messages.removeAll()
    }
    
    private func loadAIServiceFromSettings() {
        // 仅从 UserDefaults 加载，必须手动配置
        let providerRaw = UserDefaults.standard.string(forKey: "ai_provider") ?? "通义千问"
        let savedKey = UserDefaults.standard.string(forKey: "ai_api_key") ?? ""
        
        if !savedKey.isEmpty {
            let provider = AIProvider.allCases.first { $0.rawValue == providerRaw } ?? .qwen
            let baseURL = UserDefaults.standard.string(forKey: "ai_base_url") ?? provider.defaultBaseURL
            let model = UserDefaults.standard.string(forKey: "ai_model") ?? provider.defaultModel
            
            aiService = OpenAIService(apiKey: savedKey, model: model, baseURL: baseURL, provider: provider)
            selectedProvider = provider
        }
        // 未配置时 aiService 保持 nil，用户需手动配置
    }
    
    private func saveAPIConfig() {
        guard !apiKeyInput.isEmpty else { return }
        
        let baseURL = baseURLInput.isEmpty ? selectedProvider.defaultBaseURL : baseURLInput
        let model = modelInput.isEmpty ? selectedProvider.defaultModel : modelInput
        
        // 保存到 UserDefaults
        UserDefaults.standard.set(selectedProvider.rawValue, forKey: "ai_provider")
        UserDefaults.standard.set(apiKeyInput, forKey: "ai_api_key")
        UserDefaults.standard.set(baseURL, forKey: "ai_base_url")
        UserDefaults.standard.set(model, forKey: "ai_model")
        
        // 创建服务
        aiService = OpenAIService(apiKey: apiKeyInput, model: model, baseURL: baseURL, provider: selectedProvider)
        
        showAPIConfig = false
        
        // 添加系统消息
        let systemMsg = ChatMessage(
            role: .assistant,
            content: "已连接 \(selectedProvider.rawValue) API，模型：\(model)"
        )
        messages.append(systemMsg)
    }
}

// MARK: - API 配置面板

struct APIConfigSheet: View {
    @Binding var selectedProvider: AIProvider
    @Binding var apiKeyInput: String
    @Binding var baseURLInput: String
    @Binding var modelInput: String
    let onSave: () -> Void
    let onCancel: () -> Void
    
    var body: some View {
        VStack(spacing: 0) {
            // 头部
            HStack {
                Text("配置 AI 服务")
                    .font(.title2)
                    .fontWeight(.bold)
                Spacer()
                Button(action: onCancel) {
                    Image(systemName: "xmark.circle.fill")
                        .font(.title2)
                        .foregroundColor(.secondary)
                }
                .buttonStyle(.plain)
            }
            .padding()
            
            Divider()
            
            // 配置表单
            Form {
                Section("服务提供商") {
                    Picker("提供商", selection: $selectedProvider) {
                        ForEach(AIProvider.allCases, id: \.self) { provider in
                            Text(provider.rawValue).tag(provider)
                        }
                    }
                    .pickerStyle(.segmented)
                    .onChange(of: selectedProvider) { _, newValue in
                        baseURLInput = newValue.defaultBaseURL
                        modelInput = newValue.defaultModel
                    }
                }
                
                Section("API 配置") {
                    LabeledContent("API Key") {
                        SecureField("输入 API Key", text: $apiKeyInput)
                            .textFieldStyle(.roundedBorder)
                    }
                    
                    LabeledContent("Base URL") {
                        TextField(selectedProvider.defaultBaseURL, text: $baseURLInput)
                            .textFieldStyle(.roundedBorder)
                    }
                    
                    LabeledContent("模型") {
                        TextField(selectedProvider.defaultModel, text: $modelInput)
                            .textFieldStyle(.roundedBorder)
                    }
                }
                
                Section("说明") {
                    switch selectedProvider {
                    case .qwen:
                        Text("""
                        **通义千问配置**
                        
                        1. 前往 [阿里云 DashScope](https://dashscope.console.aliyun.com/) 获取 API Key
                        2. 推荐模型：qwen-plus、qwen-turbo、qwen-max
                        
                        环境变量：`DASHSCOPE_API_KEY`
                        """)
                    case .openai:
                        Text("""
                        **OpenAI 配置**
                        
                        1. 前往 [OpenAI Platform](https://platform.openai.com/) 获取 API Key
                        2. 推荐模型：gpt-4o-mini、gpt-4o
                        
                        环境变量：`OPENAI_API_KEY`
                        """)
                    case .custom:
                        Text("""
                        **自定义配置**
                        
                        支持任何 OpenAI 兼容的 API 服务：
                        - Azure OpenAI
                        - Anthropic (Claude)
                        - 本地 Ollama
                        - 其他代理服务
                        """)
                    }
                }
            }
            .formStyle(.grouped)
            
            Divider()
            
            // 操作按钮
            HStack {
                Button("取消", action: onCancel)
                    .buttonStyle(.bordered)
                
                Spacer()
                
                Button(action: onSave) {
                    Label("保存并连接", systemImage: "checkmark.circle")
                }
                .buttonStyle(.borderedProminent)
                .disabled(apiKeyInput.isEmpty)
            }
            .padding()
        }
        .frame(width: 500, height: 500)
    }
}

// MARK: - 数据模型

struct ChatMessage: Identifiable {
    let id = UUID()
    let role: Role
    let content: String
    let actions: [AIAction]
    let timestamp = Date()
    
    enum Role {
        case user
        case assistant
    }
    
    init(role: Role, content: String, actions: [AIAction] = []) {
        self.role = role
        self.content = content
        self.actions = actions
    }
}

enum AIAction {
    case rename(propertyId: UUID, newName: String)
    case setSemanticType(propertyId: UUID, type: MetaProperty.SemanticType)
    case setDescription(propertyId: UUID, description: String)
    case setUnit(propertyId: UUID, unit: String)
    
    var propertyId: UUID {
        switch self {
        case .rename(let id, _): return id
        case .setSemanticType(let id, _): return id
        case .setDescription(let id, _): return id
        case .setUnit(let id, _): return id
        }
    }
}

struct AIResponse {
    let message: String
    let actions: [AIAction]
}

// MARK: - 子视图

struct WelcomeMessage: View {
    let objectName: String
    let propertyCount: Int
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "sparkles")
                    .foregroundColor(.xingtuAccent)
                Text("AI 元数据助手")
                    .fontWeight(.medium)
            }
            
            Text("你好！我可以帮你修改「\(objectName)」的元数据（共 \(propertyCount) 个字段）。")
            
            Text("试试这些指令：")
                .foregroundColor(.secondary)
            
            VStack(alignment: .leading, spacing: 8) {
                SuggestionChip(text: "把第一列改名为「公司名称」")
                SuggestionChip(text: "把 amount 标记为金额类型")
                SuggestionChip(text: "给所有字段添加中文名称")
            }
        }
        .padding()
        .background(Color.xingtuSecondaryBackground)
        .cornerRadius(12)
    }
}

struct SuggestionChip: View {
    let text: String
    
    var body: some View {
        Text(text)
            .font(.caption)
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(Color.xingtuAccent.opacity(0.15))
            .foregroundColor(.xingtuAccent)
            .cornerRadius(16)
    }
}

struct MessageBubble: View {
    let message: ChatMessage
    
    var body: some View {
        HStack {
            if message.role == .user {
                Spacer()
            }
            
            VStack(alignment: message.role == .user ? .trailing : .leading, spacing: 4) {
                Text(try! AttributedString(markdown: message.content))
                    .padding(12)
                    .background(
                        message.role == .user
                            ? Color.xingtuAccent
                            : Color.xingtuSecondaryBackground
                    )
                    .foregroundColor(message.role == .user ? .white : .primary)
                    .cornerRadius(16)
                
                // 显示执行的动作
                if !message.actions.isEmpty {
                    HStack(spacing: 4) {
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundColor(.green)
                        Text("已执行 \(message.actions.count) 项修改")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
            }
            
            if message.role == .assistant {
                Spacer()
            }
        }
    }
}
