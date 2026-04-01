// XingJiScheduler.swift
// 星图 - 行技调度器
// 版本: v0.2.0

import Foundation

// MARK: - 行技协议

/// 行技协议 - 所有行技必须遵循
public protocol XingJiProtocol {
    /// 行技 ID
    var id: String { get }
    
    /// 行技版本
    var version: String { get }
    
    /// 行技名称
    var name: String { get }
    
    /// 执行行技
    func execute(context: XingJiContext) async throws -> XingJiResult
}

// MARK: - 行技上下文

/// 行技执行上下文
public struct XingJiContext: Sendable {
    public let executionId: UUID
    public let correlationId: UUID
    public let triggerEvent: any EventProtocol
    public let params: [String: Any]
    
    public init(
        executionId: UUID = UUID(),
        correlationId: UUID,
        triggerEvent: any EventProtocol,
        params: [String: Any] = [:]
    ) {
        self.executionId = executionId
        self.correlationId = correlationId
        self.triggerEvent = triggerEvent
        self.params = params
    }
    
    public func getParam<T>(_ key: String) -> T? {
        return params[key] as? T
    }
}

// MARK: - 行技结果

/// 行技执行结果
public struct XingJiResult: Sendable {
    public let success: Bool
    public let output: [String: Any]
    public let decisionsCount: Int
    public let appliedCount: Int
    public let queuedCount: Int
    public let errorMessage: String?
    
    public init(
        success: Bool,
        output: [String: Any] = [:],
        decisionsCount: Int = 0,
        appliedCount: Int = 0,
        queuedCount: Int = 0,
        errorMessage: String? = nil
    ) {
        self.success = success
        self.output = output
        self.decisionsCount = decisionsCount
        self.appliedCount = appliedCount
        self.queuedCount = queuedCount
        self.errorMessage = errorMessage
    }
    
    public static func success(output: [String: Any] = [:]) -> XingJiResult {
        return XingJiResult(success: true, output: output)
    }
    
    public static func failure(_ message: String) -> XingJiResult {
        return XingJiResult(success: false, errorMessage: message)
    }
}

// MARK: - 执行状态

/// 行技执行状态
public enum ExecutionStatus: String, Codable, Sendable {
    case pending
    case running
    case completed
    case failed
    case cancelled
}

// MARK: - 执行记录

/// 行技执行记录
public struct XingJiExecution: Identifiable, Sendable {
    public let id: UUID
    public let xingjiId: String
    public let correlationId: UUID
    public let triggerEventId: UUID
    public var status: ExecutionStatus
    public var currentCell: String?
    public var progress: Double
    public var result: XingJiResult?
    public let createdAt: Date
    public var startedAt: Date?
    public var completedAt: Date?
    
    public var durationMs: Int? {
        guard let start = startedAt, let end = completedAt else { return nil }
        return Int(end.timeIntervalSince(start) * 1000)
    }
}

// MARK: - 行技调度器

/// 行技调度器 - 序律腺核心组件
public actor XingJiScheduler {
    
    // MARK: - 单例
    
    public static let shared = XingJiScheduler()
    
    // MARK: - 属性
    
    private var rules: [TriggerRule] = TriggerRule.defaultRules
    private var registeredXingJi: [String: any XingJiProtocol] = [:]
    private var executions: [UUID: XingJiExecution] = [:]
    private var eventBus: EventBus
    private var subscriptionId: UUID?
    
    // 配置
    private let maxConcurrent: Int = 5
    private var runningCount: Int = 0
    private var pendingQueue: [(any EventProtocol, TriggerRule)] = []
    
    // MARK: - 初始化
    
    public init(eventBus: EventBus = .shared) {
        self.eventBus = eventBus
    }
    
    // MARK: - 启动/停止
    
    /// 启动调度器
    public func start() async {
        guard subscriptionId == nil else { return }
        
        // 订阅所有事件
        subscriptionId = await eventBus.subscribeAll { [weak self] event in
            await self?.handleEvent(event)
        }
        
        print("🚀 [XingJiScheduler] 调度器已启动，监听 \(rules.count) 条规则")
    }
    
    /// 停止调度器
    public func stop() async {
        if let id = subscriptionId {
            await eventBus.unsubscribe(id)
            subscriptionId = nil
        }
        print("⏹ [XingJiScheduler] 调度器已停止")
    }
    
    // MARK: - 规则管理
    
    /// 添加规则
    public func addRule(_ rule: TriggerRule) {
        rules.append(rule)
    }
    
    /// 移除规则
    public func removeRule(_ ruleId: String) {
        rules.removeAll { $0.id == ruleId }
    }
    
    /// 启用/禁用规则
    public func setRuleEnabled(_ ruleId: String, enabled: Bool) {
        if let index = rules.firstIndex(where: { $0.id == ruleId }) {
            var rule = rules[index]
            rule = TriggerRule(
                id: rule.id,
                name: rule.name,
                description: rule.description,
                eventType: rule.eventType,
                condition: rule.condition,
                action: rule.action,
                priority: rule.priority,
                delayMs: rule.delayMs,
                batchWindowMs: rule.batchWindowMs,
                enabled: enabled
            )
            rules[index] = rule
        }
    }
    
    // MARK: - 行技注册
    
    /// 注册行技
    public func registerXingJi(_ xingji: any XingJiProtocol) {
        registeredXingJi[xingji.id] = xingji
        print("📝 [XingJiScheduler] 注册行技: \(xingji.id)")
    }
    
    /// 注销行技
    public func unregisterXingJi(_ xingjiId: String) {
        registeredXingJi.removeValue(forKey: xingjiId)
    }
    
    // MARK: - 事件处理
    
    /// 处理事件
    private func handleEvent(_ event: any EventProtocol) async {
        // 找到匹配的规则
        let matchedRules = rules.filter { rule in
            guard rule.enabled && rule.eventType == event.type else { return false }
            
            // 评估条件
            if let condition = rule.condition {
                // 将事件转换为字典进行条件评估
                let payload = eventToPayload(event)
                return condition.evaluate(payload: payload)
            }
            
            return true
        }
        
        // 按优先级排序
        let sortedRules = matchedRules.sorted { $0.priority > $1.priority }
        
        // 处理每个匹配的规则
        for rule in sortedRules {
            await processRule(rule, event: event)
        }
    }
    
    /// 处理规则
    private func processRule(_ rule: TriggerRule, event: any EventProtocol) async {
        switch rule.action.type {
        case .startXingji:
            await scheduleXingJi(rule: rule, event: event)
            
        case .addToReviewQueue:
            // TODO: 添加到审核队列
            print("📋 [XingJiScheduler] 添加到审核队列")
            
        case .notify:
            // TODO: 发送通知
            print("🔔 [XingJiScheduler] 发送通知")
            
        case .log:
            print("📝 [XingJiScheduler] 日志: \(event.type.rawValue)")
        @unknown default:
            break
        }
    }
    
    /// 调度行技执行
    private func scheduleXingJi(rule: TriggerRule, event: any EventProtocol) async {
        guard let xingjiId = rule.action.xingjiId else {
            print("⚠️ [XingJiScheduler] 规则 \(rule.id) 缺少 xingji_id")
            return
        }
        
        guard let xingji = registeredXingJi[xingjiId] else {
            print("⚠️ [XingJiScheduler] 行技未注册: \(xingjiId)")
            return
        }
        
        // 检查并发限制
        if runningCount >= maxConcurrent {
            pendingQueue.append((event, rule))
            print("⏳ [XingJiScheduler] 行技排队: \(xingjiId)")
            return
        }
        
        // 延迟执行
        if rule.delayMs > 0 {
            try? await Task.sleep(nanoseconds: UInt64(rule.delayMs) * 1_000_000)
        }
        
        // 创建执行记录
        let executionId = UUID()
        let correlationId = event.correlationId ?? event.id
        
        var execution = XingJiExecution(
            id: executionId,
            xingjiId: xingjiId,
            correlationId: correlationId,
            triggerEventId: event.id,
            status: .pending,
            progress: 0,
            createdAt: Date()
        )
        
        executions[executionId] = execution
        
        // 发布行技启动事件
        await eventBus.publish(XingJiStartedEvent(
            correlationId: correlationId,
            executionId: executionId,
            xingjiId: xingjiId,
            triggerEventId: event.id,
            targetObjectId: nil  // TODO: 从事件中提取
        ))
        
        // 执行行技
        runningCount += 1
        execution.status = .running
        execution.startedAt = Date()
        executions[executionId] = execution
        
        do {
            let context = XingJiContext(
                executionId: executionId,
                correlationId: correlationId,
                triggerEvent: event
            )
            
            let result = try await xingji.execute(context: context)
            
            execution.status = result.success ? .completed : .failed
            execution.result = result
            execution.completedAt = Date()
            executions[executionId] = execution
            
            // 发布完成事件
            await eventBus.publish(Event(
                type: result.success ? .xingjiCompleted : .xingjiFailed,
                source: "xingji_scheduler",
                correlationId: correlationId,
                payload: [
                    "execution_id": AnyCodable(executionId.uuidString),
                    "xingji_id": AnyCodable(xingjiId),
                    "success": AnyCodable(result.success),
                    "decisions_count": AnyCodable(result.decisionsCount),
                    "applied_count": AnyCodable(result.appliedCount),
                    "queued_count": AnyCodable(result.queuedCount)
                ]
            ))
            
            print("✅ [XingJiScheduler] 行技完成: \(xingjiId)")
            
        } catch {
            execution.status = .failed
            execution.result = XingJiResult.failure(error.localizedDescription)
            execution.completedAt = Date()
            executions[executionId] = execution
            
            print("❌ [XingJiScheduler] 行技失败: \(xingjiId) - \(error)")
        }
        
        runningCount -= 1
        
        // 处理队列中的待执行任务
        if !pendingQueue.isEmpty {
            let (nextEvent, nextRule) = pendingQueue.removeFirst()
            await processRule(nextRule, event: nextEvent)
        }
    }
    
    // MARK: - 辅助方法
    
    /// 将事件转换为 payload 字典
    private func eventToPayload(_ event: any EventProtocol) -> [String: Any] {
        var payload: [String: Any] = [
            "id": event.id.uuidString,
            "type": event.type.rawValue,
            "timestamp": event.timestamp,
            "source": event.source
        ]
        
        // 添加事件特定字段
        if let fileEvent = event as? FileDroppedEvent {
            payload["filePath"] = fileEvent.filePath
            payload["fileType"] = fileEvent.fileType
            payload["fileSize"] = fileEvent.fileSize
            payload["fileName"] = fileEvent.fileName
        } else if let objectEvent = event as? ObjectCreatedEvent {
            payload["objectId"] = objectEvent.objectId.uuidString
            payload["objectName"] = objectEvent.objectName
            payload["objectType"] = objectEvent.objectType
            payload["status"] = objectEvent.status
        }
        // 添加更多事件类型...
        
        return payload
    }
    
    // MARK: - 状态查询
    
    /// 获取执行记录
    public func getExecution(_ id: UUID) -> XingJiExecution? {
        return executions[id]
    }
    
    /// 获取运行中的执行
    public func getRunningExecutions() -> [XingJiExecution] {
        return executions.values.filter { $0.status == .running }
    }
    
    /// 获取最近的执行记录
    public func getRecentExecutions(limit: Int = 10) -> [XingJiExecution] {
        return Array(executions.values
            .sorted { $0.createdAt > $1.createdAt }
            .prefix(limit))
    }
}

// MARK: - 手动触发

extension XingJiScheduler {
    
    /// 手动触发行技
    public func triggerXingJi(
        _ xingjiId: String,
        correlationId: UUID = UUID(),
        params: [String: Any] = [:]
    ) async throws -> XingJiResult {
        guard let xingji = registeredXingJi[xingjiId] else {
            throw XingJiError.notFound(xingjiId)
        }
        
        // 创建一个虚拟事件
        let dummyEvent = Event(
            type: .xingjiStarted,
            source: "manual",
            correlationId: correlationId
        )
        
        let context = XingJiContext(
            correlationId: correlationId,
            triggerEvent: dummyEvent,
            params: params
        )
        
        return try await xingji.execute(context: context)
    }
}

// MARK: - 错误类型

public enum XingJiError: Error, LocalizedError {
    case notFound(String)
    case executionFailed(String)
    case timeout
    case cancelled
    
    public var errorDescription: String? {
        switch self {
        case .notFound(let id):
            return "行技未找到: \(id)"
        case .executionFailed(let message):
            return "执行失败: \(message)"
        case .timeout:
            return "执行超时"
        case .cancelled:
            return "执行已取消"
        }
    }
}
