// 星图 (XingTu) - CSV 解析器
// 核心引擎

import Foundation

/// CSV 解析器协议
public protocol CSVParserProtocol {
    func parse(url: URL) async throws -> ParseResult
    func preview(url: URL, rows: Int) async throws -> [[String]]
    func inferTypes(columns: [String], samples: [[String]]) -> [DataTypeInference]
}

/// 解析结果
public struct ParseResult {
    public let columns: [ColumnInfo]
    public let rowCount: Int
    public let sampleData: [[String]]
    public let encoding: String
    
    public init(
        columns: [ColumnInfo],
        rowCount: Int,
        sampleData: [[String]],
        encoding: String
    ) {
        self.columns = columns
        self.rowCount = rowCount
        self.sampleData = sampleData
        self.encoding = encoding
    }
}

/// 列信息
public struct ColumnInfo {
    public let index: Int
    public let name: String
    public let inferredType: MetaProperty.DataType
    public let nullCount: Int
    public let uniqueCount: Int
    public let sampleValues: [String]
    
    public init(
        index: Int,
        name: String,
        inferredType: MetaProperty.DataType,
        nullCount: Int,
        uniqueCount: Int,
        sampleValues: [String]
    ) {
        self.index = index
        self.name = name
        self.inferredType = inferredType
        self.nullCount = nullCount
        self.uniqueCount = uniqueCount
        self.sampleValues = sampleValues
    }
}

/// 数据类型推断结果
public struct DataTypeInference {
    public let columnIndex: Int
    public let dataType: MetaProperty.DataType
    public let confidence: Double
    
    public init(columnIndex: Int, dataType: MetaProperty.DataType, confidence: Double) {
        self.columnIndex = columnIndex
        self.dataType = dataType
        self.confidence = confidence
    }
}

/// CSV 解析器实现
public class CSVParser: CSVParserProtocol {
    
    // MARK: - 配置
    
    public struct Config {
        public var delimiter: Character
        public var encoding: String.Encoding
        public var hasHeader: Bool
        public var maxPreviewRows: Int
        public var maxSampleValues: Int
        
        public static let `default` = Config(
            delimiter: ",",
            encoding: .utf8,
            hasHeader: true,
            maxPreviewRows: 100,
            maxSampleValues: 10
        )
        
        public init(
            delimiter: Character = ",",
            encoding: String.Encoding = .utf8,
            hasHeader: Bool = true,
            maxPreviewRows: Int = 100,
            maxSampleValues: Int = 10
        ) {
            self.delimiter = delimiter
            self.encoding = encoding
            self.hasHeader = hasHeader
            self.maxPreviewRows = maxPreviewRows
            self.maxSampleValues = maxSampleValues
        }
    }
    
    private var config: Config
    
    public init(config: Config = .default) {
        self.config = config
    }
    
    // MARK: - 解析
    
    public func parse(url: URL) async throws -> ParseResult {
        // 检测编码
        let detectedEncoding = detectEncoding(url: url)
        config.encoding = detectedEncoding.encoding
        
        // 读取文件
        let content = try String(contentsOf: url, encoding: config.encoding)
        let lines = content.components(separatedBy: .newlines).filter { !$0.isEmpty }
        
        guard !lines.isEmpty else {
            throw CSVParserError.emptyFile
        }
        
        // 检测分隔符
        config.delimiter = detectDelimiter(firstLine: lines[0])
        
        // 解析表头
        let headerLine = lines[0]
        let headers = parseLine(headerLine)
        
        guard !headers.isEmpty else {
            throw CSVParserError.noColumns
        }
        
        // 解析数据行
        let dataLines = Array(lines.dropFirst())
        let rowCount = dataLines.count
        
        // 收集列统计信息
        var columnData: [[String]] = Array(repeating: [], count: headers.count)
        var nullCounts = Array(repeating: 0, count: headers.count)
        var uniqueSets: [Set<String>] = Array(repeating: Set(), count: headers.count)
        
        let previewLimit = min(config.maxPreviewRows, rowCount)
        var sampleData: [[String]] = []
        
        for (lineIndex, line) in dataLines.enumerated() {
            let values = parseLine(line)
            
            // 补齐或截断到表头长度
            var normalizedValues = values
            while normalizedValues.count < headers.count {
                normalizedValues.append("")
            }
            if normalizedValues.count > headers.count {
                normalizedValues = Array(normalizedValues.prefix(headers.count))
            }
            
            // 收集预览数据
            if lineIndex < previewLimit {
                sampleData.append(normalizedValues)
            }
            
            // 统计每列
            for (colIndex, value) in normalizedValues.enumerated() {
                let trimmed = value.trimmingCharacters(in: .whitespaces)
                
                if trimmed.isEmpty {
                    nullCounts[colIndex] += 1
                } else {
                    uniqueSets[colIndex].insert(trimmed)
                    if columnData[colIndex].count < config.maxSampleValues {
                        if !columnData[colIndex].contains(trimmed) {
                            columnData[colIndex].append(trimmed)
                        }
                    }
                }
            }
        }
        
        // 推断类型
        let typeInferences = inferTypes(columns: headers, samples: sampleData)
        
        // 构建列信息
        var columns: [ColumnInfo] = []
        for (index, header) in headers.enumerated() {
            let inference = typeInferences.first { $0.columnIndex == index }
            columns.append(ColumnInfo(
                index: index,
                name: header,
                inferredType: inference?.dataType ?? .unknown,
                nullCount: nullCounts[index],
                uniqueCount: uniqueSets[index].count,
                sampleValues: columnData[index]
            ))
        }
        
        return ParseResult(
            columns: columns,
            rowCount: rowCount,
            sampleData: sampleData,
            encoding: detectedEncoding.name
        )
    }
    
    public func preview(url: URL, rows: Int) async throws -> [[String]] {
        let content = try String(contentsOf: url, encoding: config.encoding)
        let lines = content.components(separatedBy: .newlines).filter { !$0.isEmpty }
        
        let limit = min(rows + 1, lines.count)  // +1 for header
        var result: [[String]] = []
        
        for i in 0..<limit {
            result.append(parseLine(lines[i]))
        }
        
        return result
    }
    
    public func inferTypes(columns: [String], samples: [[String]]) -> [DataTypeInference] {
        var inferences: [DataTypeInference] = []
        
        for colIndex in 0..<columns.count {
            let columnValues = samples.compactMap { row -> String? in
                guard colIndex < row.count else { return nil }
                let value = row[colIndex].trimmingCharacters(in: .whitespaces)
                return value.isEmpty ? nil : value
            }
            
            let inference = inferColumnType(values: columnValues)
            inferences.append(DataTypeInference(
                columnIndex: colIndex,
                dataType: inference.type,
                confidence: inference.confidence
            ))
        }
        
        return inferences
    }
    
    // MARK: - 私有方法
    
    private func parseLine(_ line: String) -> [String] {
        var result: [String] = []
        var current = ""
        var inQuotes = false
        
        for char in line {
            if char == "\"" {
                inQuotes.toggle()
            } else if char == config.delimiter && !inQuotes {
                result.append(current.trimmingCharacters(in: .whitespaces))
                current = ""
            } else {
                current.append(char)
            }
        }
        
        result.append(current.trimmingCharacters(in: .whitespaces))
        
        // 移除引号
        return result.map { value in
            var v = value
            if v.hasPrefix("\"") && v.hasSuffix("\"") && v.count >= 2 {
                v.removeFirst()
                v.removeLast()
            }
            return v
        }
    }
    
    private func detectDelimiter(firstLine: String) -> Character {
        let delimiters: [Character] = [",", "\t", ";", "|"]
        var maxCount = 0
        var bestDelimiter: Character = ","
        
        for delimiter in delimiters {
            let count = firstLine.filter { $0 == delimiter }.count
            if count > maxCount {
                maxCount = count
                bestDelimiter = delimiter
            }
        }
        
        return bestDelimiter
    }
    
    private func detectEncoding(url: URL) -> (encoding: String.Encoding, name: String) {
        // 尝试读取 BOM
        if let data = try? Data(contentsOf: url, options: .mappedIfSafe) {
            if data.starts(with: [0xEF, 0xBB, 0xBF]) {
                return (.utf8, "UTF-8 (BOM)")
            }
            if data.starts(with: [0xFF, 0xFE]) {
                return (.utf16LittleEndian, "UTF-16 LE")
            }
            if data.starts(with: [0xFE, 0xFF]) {
                return (.utf16BigEndian, "UTF-16 BE")
            }
        }
        
        // 尝试 UTF-8
        if let _ = try? String(contentsOf: url, encoding: .utf8) {
            return (.utf8, "UTF-8")
        }
        
        // 尝试 GBK (中文 Windows)
        let gbkEncoding = String.Encoding(rawValue: CFStringConvertEncodingToNSStringEncoding(CFStringEncoding(CFStringEncodings.GB_18030_2000.rawValue)))
        if let _ = try? String(contentsOf: url, encoding: gbkEncoding) {
            return (gbkEncoding, "GBK")
        }
        
        // 默认 UTF-8
        return (.utf8, "UTF-8")
    }
    
    private func inferColumnType(values: [String]) -> (type: MetaProperty.DataType, confidence: Double) {
        guard !values.isEmpty else {
            return (.unknown, 0)
        }
        
        var intCount = 0
        var decimalCount = 0
        var boolCount = 0
        var dateCount = 0
        var datetimeCount = 0
        
        for value in values {
            if isInteger(value) {
                intCount += 1
            } else if isDecimal(value) {
                decimalCount += 1
            } else if isBoolean(value) {
                boolCount += 1
            } else if isDatetime(value) {
                datetimeCount += 1
            } else if isDate(value) {
                dateCount += 1
            }
        }
        
        let total = Double(values.count)
        
        // 按优先级判断
        if Double(intCount) / total >= 0.9 {
            return (.integer, Double(intCount) / total)
        }
        if Double(decimalCount + intCount) / total >= 0.9 {
            return (.decimal, Double(decimalCount + intCount) / total)
        }
        if Double(boolCount) / total >= 0.9 {
            return (.boolean, Double(boolCount) / total)
        }
        if Double(datetimeCount) / total >= 0.8 {
            return (.datetime, Double(datetimeCount) / total)
        }
        if Double(dateCount) / total >= 0.8 {
            return (.date, Double(dateCount) / total)
        }
        
        return (.string, 1.0)
    }
    
    private func isInteger(_ value: String) -> Bool {
        return Int(value) != nil
    }
    
    private func isDecimal(_ value: String) -> Bool {
        return Double(value) != nil && value.contains(".")
    }
    
    private func isBoolean(_ value: String) -> Bool {
        let lower = value.lowercased()
        return ["true", "false", "yes", "no", "1", "0", "是", "否"].contains(lower)
    }
    
    private func isDate(_ value: String) -> Bool {
        let patterns = [
            "^\\d{4}-\\d{2}-\\d{2}$",           // 2024-01-01
            "^\\d{4}/\\d{2}/\\d{2}$",           // 2024/01/01
            "^\\d{2}-\\d{2}-\\d{4}$",           // 01-01-2024
            "^\\d{2}/\\d{2}/\\d{4}$"            // 01/01/2024
        ]
        return matchesAnyPattern(value, patterns: patterns)
    }
    
    private func isDatetime(_ value: String) -> Bool {
        let patterns = [
            "^\\d{4}-\\d{2}-\\d{2}[T ]\\d{2}:\\d{2}",  // 2024-01-01T10:00 or 2024-01-01 10:00
            "^\\d{4}/\\d{2}/\\d{2} \\d{2}:\\d{2}"       // 2024/01/01 10:00
        ]
        return matchesAnyPattern(value, patterns: patterns)
    }
    
    private func matchesAnyPattern(_ value: String, patterns: [String]) -> Bool {
        for pattern in patterns {
            if let regex = try? NSRegularExpression(pattern: pattern),
               regex.firstMatch(in: value, range: NSRange(value.startIndex..., in: value)) != nil {
                return true
            }
        }
        return false
    }
    
    // MARK: - 错误
    
    public enum CSVParserError: Error, LocalizedError {
        case fileNotFound
        case emptyFile
        case noColumns
        case encodingError
        case parseError(String)
        
        public var errorDescription: String? {
            switch self {
            case .fileNotFound: return "文件不存在"
            case .emptyFile: return "文件为空"
            case .noColumns: return "未找到列"
            case .encodingError: return "编码错误"
            case .parseError(let msg): return "解析错误: \(msg)"
            }
        }
    }
}
