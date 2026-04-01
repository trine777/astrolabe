#!/usr/bin/env python3
"""星图 MCP Server - 让 AI 也能使用星图数据系统

独立实现 MCP 协议，兼容 Python 3.9+
"""

import json
import sys
from typing import Any, Dict, List, Optional

from .db import XingTuDB

# 数据库实例
db = XingTuDB()


# ==================== MCP 协议实现 ====================

class MCPServer:
    """简化的 MCP Server 实现"""
    
    def __init__(self, name: str = "xingtu"):
        self.name = name
        self.tools = self._define_tools()
        self.resources = self._define_resources()
    
    def _define_tools(self) -> List[Dict[str, Any]]:
        """定义所有工具"""
        return [
            # 对象管理
            {
                "name": "xingtu_list_objects",
                "description": "列出所有数据源对象。可按状态(draft/confirmed/published)筛选。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": ["draft", "confirmed", "published", "archived"],
                            "description": "按状态筛选（可选）"
                        },
                        "limit": {
                            "type": "integer",
                            "default": 50,
                            "description": "返回数量限制"
                        }
                    }
                }
            },
            {
                "name": "xingtu_get_object",
                "description": "获取单个数据源对象的详细信息，包括属性和关系。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "object_id": {"type": "string", "description": "对象 UUID"}
                    },
                    "required": ["object_id"]
                }
            },
            {
                "name": "xingtu_create_object",
                "description": "创建新的数据源对象（草稿状态）。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "业务名称"},
                        "original_name": {"type": "string", "description": "原始名称"},
                        "object_type": {
                            "type": "string",
                            "enum": ["csvFile", "table", "view", "derived", "external"],
                            "default": "csvFile"
                        },
                        "description": {"type": "string"},
                        "file_path": {"type": "string"},
                        "row_count": {"type": "integer"},
                        "tags": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["name", "original_name"]
                }
            },
            {
                "name": "xingtu_update_object",
                "description": "更新数据源对象的信息。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "object_id": {"type": "string"},
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["object_id"]
                }
            },
            {
                "name": "xingtu_confirm_object",
                "description": "确认对象的元数据（从 draft 变为 confirmed）。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "object_id": {"type": "string"},
                        "confirmed_by": {
                            "type": "string",
                            "enum": ["ai", "human"],
                            "default": "ai"
                        }
                    },
                    "required": ["object_id"]
                }
            },
            {
                "name": "xingtu_publish_object",
                "description": "发布对象（从 confirmed 变为 published）。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "object_id": {"type": "string"}
                    },
                    "required": ["object_id"]
                }
            },
            # 属性管理
            {
                "name": "xingtu_get_properties",
                "description": "获取对象的所有属性（列）信息。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "object_id": {"type": "string"}
                    },
                    "required": ["object_id"]
                }
            },
            {
                "name": "xingtu_create_property",
                "description": "为对象创建新属性。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "object_id": {"type": "string"},
                        "original_name": {"type": "string"},
                        "data_type": {
                            "type": "string",
                            "enum": ["string", "integer", "decimal", "boolean", "date", "datetime", "json", "unknown"]
                        },
                        "sample_values": {"type": "array", "items": {"type": "string"}},
                        "display_name": {"type": "string"},
                        "semantic_type": {"type": "string"},
                        "description": {"type": "string"}
                    },
                    "required": ["object_id", "original_name", "data_type"]
                }
            },
            {
                "name": "xingtu_update_property",
                "description": "更新属性的语义信息。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "property_id": {"type": "string"},
                        "display_name": {"type": "string"},
                        "semantic_type": {"type": "string"},
                        "description": {"type": "string"},
                        "unit": {"type": "string"},
                        "ai_inferred": {"type": "object"}
                    },
                    "required": ["property_id"]
                }
            },
            # 关系管理
            {
                "name": "xingtu_get_relations",
                "description": "获取与对象相关的所有关系。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "object_id": {"type": "string"}
                    },
                    "required": ["object_id"]
                }
            },
            {
                "name": "xingtu_create_relation",
                "description": "创建两个数据源之间的关系（AI 提议）。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "source_object_id": {"type": "string"},
                        "source_property_id": {"type": "string"},
                        "target_object_id": {"type": "string"},
                        "target_property_id": {"type": "string"},
                        "relation_type": {
                            "type": "string",
                            "enum": ["oneToOne", "oneToMany", "manyToOne", "manyToMany"]
                        },
                        "relation_name": {"type": "string"},
                        "description": {"type": "string"},
                        "confidence": {"type": "number"}
                    },
                    "required": ["source_object_id", "source_property_id",
                                "target_object_id", "target_property_id", "relation_type"]
                }
            },
            {
                "name": "xingtu_confirm_relation",
                "description": "确认 AI 提议的关系。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "relation_id": {"type": "string"}
                    },
                    "required": ["relation_id"]
                }
            },
            # 事件与世界模型
            {
                "name": "xingtu_get_events",
                "description": "获取事件历史（影澜轩）。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "object_id": {"type": "string"},
                        "limit": {"type": "integer", "default": 50}
                    }
                }
            },
            {
                "name": "xingtu_emit_event",
                "description": "AI 发送事件到影澜轩。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "event_type": {
                            "type": "string",
                            "enum": ["insight_generated", "anomaly_detected", "suggestion_made", "analysis_completed"]
                        },
                        "object_id": {"type": "string"},
                        "description": {"type": "string"}
                    },
                    "required": ["event_type", "description"]
                }
            },
            {
                "name": "xingtu_get_world_model",
                "description": "获取完整的世界模型上下文。",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
        ]
    
    def _define_resources(self) -> List[Dict[str, Any]]:
        """定义资源"""
        return [
            {
                "uri": "xingtu://world-model",
                "name": "星图世界模型",
                "description": "所有已发布的数据源、属性和关系",
                "mimeType": "application/json"
            },
            {
                "uri": "xingtu://objects",
                "name": "数据源列表",
                "description": "所有数据源对象",
                "mimeType": "application/json"
            },
        ]
    
    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """处理 JSON-RPC 请求"""
        method = request.get("method", "")
        params = request.get("params", {})
        req_id = request.get("id")
        
        try:
            if method == "initialize":
                result = self._handle_initialize(params)
            elif method == "initialized":
                result = None
            elif method == "tools/list":
                result = {"tools": self.tools}
            elif method == "tools/call":
                result = self._handle_tool_call(params)
            elif method == "resources/list":
                result = {"resources": self.resources}
            elif method == "resources/read":
                result = self._handle_resource_read(params)
            else:
                return self._error_response(req_id, -32601, f"Method not found: {method}")
            
            return self._success_response(req_id, result)
        
        except Exception as e:
            return self._error_response(req_id, -32000, str(e))
    
    def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理初始化"""
        db.initialize()
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
                "resources": {}
            },
            "serverInfo": {
                "name": self.name,
                "version": "0.1.0"
            }
        }
    
    def _handle_tool_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理工具调用"""
        name = params.get("name", "")
        args = params.get("arguments", {})
        
        result = execute_tool(name, args)
        
        return {
            "content": [{
                "type": "text",
                "text": json.dumps(result, ensure_ascii=False, indent=2)
            }]
        }
    
    def _handle_resource_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理资源读取"""
        uri = params.get("uri", "")
        
        if uri == "xingtu://world-model":
            result = db.get_world_model()
        elif uri == "xingtu://objects":
            result = db.list_objects()
        else:
            result = {"error": f"Unknown resource: {uri}"}
        
        return {
            "contents": [{
                "uri": uri,
                "mimeType": "application/json",
                "text": json.dumps(result, ensure_ascii=False, indent=2)
            }]
        }
    
    def _success_response(self, req_id: Any, result: Any) -> Dict[str, Any]:
        """成功响应"""
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": result
        }
    
    def _error_response(self, req_id: Any, code: int, message: str) -> Dict[str, Any]:
        """错误响应"""
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": code,
                "message": message
            }
        }


# ==================== 工具执行 ====================

def execute_tool(name: str, args: Dict[str, Any]) -> Any:
    """执行工具"""
    
    # 对象操作
    if name == "xingtu_list_objects":
        return db.list_objects(
            status=args.get("status"),
            limit=args.get("limit", 50)
        )
    
    elif name == "xingtu_get_object":
        obj = db.get_object(args["object_id"])
        if not obj:
            return {"error": "对象不存在"}
        properties = db.get_properties(args["object_id"])
        relations = db.get_relations(args["object_id"])
        return {"object": obj, "properties": properties, "relations": relations}
    
    elif name == "xingtu_create_object":
        return db.create_object(
            name=args["name"],
            original_name=args["original_name"],
            object_type=args.get("object_type", "csvFile"),
            description=args.get("description"),
            file_path=args.get("file_path"),
            row_count=args.get("row_count"),
            tags=args.get("tags")
        )
    
    elif name == "xingtu_update_object":
        return db.update_object(
            object_id=args["object_id"],
            name=args.get("name"),
            description=args.get("description"),
            tags=args.get("tags")
        )
    
    elif name == "xingtu_confirm_object":
        return db.confirm_object(
            object_id=args["object_id"],
            confirmed_by=args.get("confirmed_by", "ai")
        )
    
    elif name == "xingtu_publish_object":
        return db.publish_object(args["object_id"])
    
    # 属性操作
    elif name == "xingtu_get_properties":
        return db.get_properties(args["object_id"])
    
    elif name == "xingtu_create_property":
        return db.create_property(
            object_id=args["object_id"],
            original_name=args["original_name"],
            data_type=args["data_type"],
            sample_values=args.get("sample_values"),
            null_count=args.get("null_count", 0),
            unique_count=args.get("unique_count", 0),
            display_name=args.get("display_name"),
            semantic_type=args.get("semantic_type"),
            description=args.get("description")
        )
    
    elif name == "xingtu_update_property":
        return db.update_property(
            property_id=args["property_id"],
            display_name=args.get("display_name"),
            semantic_type=args.get("semantic_type"),
            description=args.get("description"),
            unit=args.get("unit"),
            ai_inferred=args.get("ai_inferred")
        )
    
    # 关系操作
    elif name == "xingtu_get_relations":
        return db.get_relations(args["object_id"])
    
    elif name == "xingtu_create_relation":
        return db.create_relation(
            source_object_id=args["source_object_id"],
            source_property_id=args["source_property_id"],
            target_object_id=args["target_object_id"],
            target_property_id=args["target_property_id"],
            relation_type=args["relation_type"],
            relation_name=args.get("relation_name"),
            description=args.get("description"),
            confidence=args.get("confidence")
        )
    
    elif name == "xingtu_confirm_relation":
        return db.confirm_relation(args["relation_id"])
    
    # 事件与世界模型
    elif name == "xingtu_get_events":
        return db.get_events(
            object_id=args.get("object_id"),
            limit=args.get("limit", 50)
        )
    
    elif name == "xingtu_emit_event":
        db.emit_event(
            event_type=args["event_type"],
            object_id=args.get("object_id"),
            description=args["description"]
        )
        return {"success": True, "message": "事件已记录"}
    
    elif name == "xingtu_get_world_model":
        return db.get_world_model()
    
    else:
        return {"error": f"未知工具: {name}"}


# ==================== Main ====================

def main():
    """入口点 - stdio 模式"""
    server = MCPServer()
    
    # 初始化数据库
    db.initialize()
    
    # 读取循环
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue
        
        try:
            response = server.handle_request(request)
            
            if response.get("result") is not None or response.get("error") is not None:
                output = json.dumps(response, ensure_ascii=False)
                print(output, flush=True)
        
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {"code": -32000, "message": str(e)}
            }
            print(json.dumps(error_response), flush=True)


if __name__ == "__main__":
    main()
