"""星图数据库访问层 - 同步版本"""

import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

# 默认数据库路径（与 Swift 版本一致）
DEFAULT_DB_PATH = Path.home() / "Library/Application Support/XingTu/xingtu.db"


class XingTuDB:
    """星图数据库访问类（同步版本）"""
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self._ensure_db_dir()
        self._conn: Optional[sqlite3.Connection] = None
    
    def _ensure_db_dir(self):
        """确保数据库目录存在"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn
    
    def initialize(self):
        """初始化数据库表"""
        conn = self._get_connection()
        conn.executescript(INIT_SCHEMA)
        conn.commit()
    
    def close(self):
        """关闭连接"""
        if self._conn:
            self._conn.close()
            self._conn = None
    
    # ==================== 对象操作 ====================
    
    def list_objects(
        self, 
        status: Optional[str] = None,
        object_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """列出所有数据源对象"""
        conn = self._get_connection()
        query = "SELECT * FROM meta_objects WHERE 1=1"
        params = []
        
        if status:
            query += " AND status = ?"
            params.append(status)
        if object_type:
            query += " AND object_type = ?"
            params.append(object_type)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_object(self, object_id: str) -> Optional[Dict[str, Any]]:
        """获取单个对象"""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM meta_objects WHERE id = ?",
            [object_id]
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def create_object(
        self,
        name: str,
        original_name: str,
        object_type: str = "csvFile",
        description: Optional[str] = None,
        file_path: Optional[str] = None,
        row_count: Optional[int] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """创建新对象"""
        object_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        
        conn = self._get_connection()
        conn.execute(
            """INSERT INTO meta_objects 
               (id, name, original_name, object_type, description, 
                file_path, row_count, status, tags, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?)""",
            [object_id, name, original_name, object_type, description,
             file_path, row_count, json.dumps(tags) if tags else None, now, now]
        )
        conn.commit()
        
        # 记录事件
        self._emit_event("objectCreated", object_id, None, "ai", None, f"创建对象: {name}")
        
        return self.get_object(object_id)
    
    def update_object(
        self,
        object_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """更新对象"""
        updates = []
        params = []
        
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(tags))
        
        if not updates:
            return self.get_object(object_id)
        
        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(object_id)
        
        conn = self._get_connection()
        conn.execute(
            f"UPDATE meta_objects SET {', '.join(updates)} WHERE id = ?",
            params
        )
        conn.commit()
        
        self._emit_event("objectUpdated", object_id, None, "ai", None, "更新对象")
        
        return self.get_object(object_id)
    
    def confirm_object(
        self, 
        object_id: str,
        confirmed_by: str = "ai"
    ) -> Optional[Dict[str, Any]]:
        """确认对象元数据"""
        now = datetime.now().isoformat()
        
        conn = self._get_connection()
        conn.execute(
            """UPDATE meta_objects 
               SET status = 'confirmed', confirmed_at = ?, confirmed_by = ?, updated_at = ?
               WHERE id = ? AND status = 'draft'""",
            [now, confirmed_by, now, object_id]
        )
        conn.commit()
        
        actor_type = "ai" if confirmed_by == "ai" else "user"
        self._emit_event("objectConfirmed", object_id, None, actor_type, confirmed_by, "确认对象元数据")
        
        return self.get_object(object_id)
    
    def publish_object(self, object_id: str) -> Optional[Dict[str, Any]]:
        """发布对象（从 draft 或 confirmed 变为 published）"""
        now = datetime.now().isoformat()
        
        conn = self._get_connection()
        conn.execute(
            """UPDATE meta_objects 
               SET status = 'published', updated_at = ?, confirmed_at = COALESCE(confirmed_at, ?)
               WHERE id = ? AND status IN ('draft', 'confirmed')""",
            [now, now, object_id]
        )
        conn.commit()
        
        self._emit_event("objectPublished", object_id, None, "ai", None, "AI 发布对象")
        
        return self.get_object(object_id)
    
    # ==================== 属性操作 ====================
    
    def get_properties(self, object_id: str) -> List[Dict[str, Any]]:
        """获取对象的所有属性"""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM meta_properties WHERE object_id = ?",
            [object_id]
        )
        return [dict(row) for row in cursor.fetchall()]
    
    def create_property(
        self,
        object_id: str,
        original_name: str,
        data_type: str,
        sample_values: Optional[List[str]] = None,
        null_count: int = 0,
        unique_count: int = 0,
        display_name: Optional[str] = None,
        semantic_type: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """创建属性"""
        prop_id = str(uuid.uuid4())
        
        conn = self._get_connection()
        conn.execute(
            """INSERT INTO meta_properties
               (id, object_id, original_name, data_type, sample_values,
                null_count, unique_count, display_name, semantic_type, description)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [prop_id, object_id, original_name, data_type,
             json.dumps(sample_values) if sample_values else None,
             null_count, unique_count, display_name, semantic_type, description]
        )
        conn.commit()
        
        cursor = conn.execute("SELECT * FROM meta_properties WHERE id = ?", [prop_id])
        return dict(cursor.fetchone())
    
    def update_property(
        self,
        property_id: str,
        display_name: Optional[str] = None,
        semantic_type: Optional[str] = None,
        description: Optional[str] = None,
        unit: Optional[str] = None,
        ai_inferred: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """更新属性"""
        updates = []
        params = []
        
        if display_name is not None:
            updates.append("display_name = ?")
            params.append(display_name)
        if semantic_type is not None:
            updates.append("semantic_type = ?")
            params.append(semantic_type)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if unit is not None:
            updates.append("unit = ?")
            params.append(unit)
        if ai_inferred is not None:
            updates.append("ai_inferred = ?")
            params.append(json.dumps(ai_inferred))
        
        if not updates:
            return None
        
        params.append(property_id)
        
        conn = self._get_connection()
        conn.execute(
            f"UPDATE meta_properties SET {', '.join(updates)} WHERE id = ?",
            params
        )
        conn.commit()
        
        cursor = conn.execute("SELECT * FROM meta_properties WHERE id = ?", [property_id])
        row = cursor.fetchone()
        return dict(row) if row else None
    
    # ==================== 关系操作 ====================
    
    def get_relations(self, object_id: str) -> List[Dict[str, Any]]:
        """获取与对象相关的所有关系"""
        conn = self._get_connection()
        cursor = conn.execute(
            """SELECT * FROM meta_relations 
               WHERE source_object_id = ? OR target_object_id = ?""",
            [object_id, object_id]
        )
        return [dict(row) for row in cursor.fetchall()]
    
    def create_relation(
        self,
        source_object_id: str,
        source_property_id: str,
        target_object_id: str,
        target_property_id: str,
        relation_type: str,
        relation_name: Optional[str] = None,
        description: Optional[str] = None,
        is_ai_inferred: bool = True,
        confidence: Optional[float] = None
    ) -> Dict[str, Any]:
        """创建关系"""
        rel_id = str(uuid.uuid4())
        
        conn = self._get_connection()
        conn.execute(
            """INSERT INTO meta_relations
               (id, source_object_id, source_property_id, target_object_id,
                target_property_id, relation_type, relation_name, description,
                is_ai_inferred, confidence, is_confirmed)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            [rel_id, source_object_id, source_property_id, target_object_id,
             target_property_id, relation_type, relation_name, description,
             1 if is_ai_inferred else 0, confidence]
        )
        conn.commit()
        
        self._emit_event("relationCreated", source_object_id, None, "ai", None, f"创建关系: {relation_type}")
        
        cursor = conn.execute("SELECT * FROM meta_relations WHERE id = ?", [rel_id])
        return dict(cursor.fetchone())
    
    def confirm_relation(self, relation_id: str) -> Optional[Dict[str, Any]]:
        """确认关系"""
        now = datetime.now().isoformat()
        
        conn = self._get_connection()
        conn.execute(
            """UPDATE meta_relations 
               SET is_confirmed = 1, confirmed_at = ?
               WHERE id = ?""",
            [now, relation_id]
        )
        conn.commit()
        
        cursor = conn.execute("SELECT * FROM meta_relations WHERE id = ?", [relation_id])
        row = cursor.fetchone()
        return dict(row) if row else None
    
    # ==================== 事件操作 ====================
    
    def get_events(
        self,
        object_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """获取事件历史"""
        conn = self._get_connection()
        if object_id:
            cursor = conn.execute(
                """SELECT * FROM meta_events 
                   WHERE object_id = ?
                   ORDER BY timestamp DESC LIMIT ?""",
                [object_id, limit]
            )
        else:
            cursor = conn.execute(
                """SELECT * FROM meta_events 
                   ORDER BY timestamp DESC LIMIT ?""",
                [limit]
            )
        return [dict(row) for row in cursor.fetchall()]
    
    def _emit_event(
        self,
        event_type: str,
        object_id: Optional[str],
        property_id: Optional[str],
        actor_type: str,
        actor_id: Optional[str],
        description: str
    ):
        """内部：发送事件"""
        event_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        
        conn = self._get_connection()
        conn.execute(
            """INSERT INTO meta_events
               (id, timestamp, event_type, object_id, property_id,
                actor_type, actor_id, description)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [event_id, now, event_type, object_id, property_id,
             actor_type, actor_id, description]
        )
        conn.commit()
    
    def emit_event(
        self,
        event_type: str,
        object_id: Optional[str] = None,
        description: str = ""
    ):
        """发送事件（AI 使用）"""
        self._emit_event(event_type, object_id, None, "ai", None, description)
    
    # ==================== 世界模型 ====================
    
    def get_world_model(self) -> Dict[str, Any]:
        """获取完整的世界模型上下文"""
        objects = self.list_objects(status="published")
        
        all_properties = {}
        for obj in objects:
            all_properties[obj["id"]] = self.get_properties(obj["id"])
        
        conn = self._get_connection()
        cursor = conn.execute("SELECT * FROM meta_relations WHERE is_confirmed = 1")
        all_relations = [dict(row) for row in cursor.fetchall()]
        
        return {
            "objects": objects,
            "properties": all_properties,
            "relations": all_relations,
            "generated_at": datetime.now().isoformat()
        }


# 初始化 Schema
INIT_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta_objects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    original_name TEXT NOT NULL,
    object_type TEXT NOT NULL,
    description TEXT,
    file_path TEXT,
    row_count INTEGER,
    status TEXT DEFAULT 'draft',
    tags TEXT,
    created_at TEXT,
    updated_at TEXT,
    confirmed_at TEXT,
    confirmed_by TEXT
);

CREATE TABLE IF NOT EXISTS meta_properties (
    id TEXT PRIMARY KEY,
    object_id TEXT NOT NULL,
    original_name TEXT NOT NULL,
    data_type TEXT NOT NULL,
    sample_values TEXT,
    null_count INTEGER DEFAULT 0,
    unique_count INTEGER DEFAULT 0,
    display_name TEXT,
    description TEXT,
    semantic_type TEXT,
    unit TEXT,
    format TEXT,
    business_rules TEXT,
    visual_preference TEXT,
    ai_inferred TEXT,
    FOREIGN KEY (object_id) REFERENCES meta_objects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS meta_relations (
    id TEXT PRIMARY KEY,
    source_object_id TEXT NOT NULL,
    source_property_id TEXT NOT NULL,
    target_object_id TEXT NOT NULL,
    target_property_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    relation_name TEXT,
    description TEXT,
    is_ai_inferred INTEGER DEFAULT 0,
    confidence REAL,
    is_confirmed INTEGER DEFAULT 0,
    confirmed_at TEXT,
    FOREIGN KEY (source_object_id) REFERENCES meta_objects(id),
    FOREIGN KEY (target_object_id) REFERENCES meta_objects(id)
);

CREATE TABLE IF NOT EXISTS meta_events (
    id TEXT PRIMARY KEY,
    timestamp TEXT,
    event_type TEXT NOT NULL,
    object_id TEXT,
    property_id TEXT,
    actor_type TEXT NOT NULL,
    actor_id TEXT,
    before_snapshot TEXT,
    after_snapshot TEXT,
    description TEXT
);

CREATE TABLE IF NOT EXISTS metric_defs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    description TEXT,
    formula TEXT NOT NULL,
    source_object_ids TEXT,
    unit TEXT,
    aggregation_type TEXT,
    dimensions TEXT,
    tags TEXT,
    status TEXT DEFAULT 'draft',
    created_at TEXT,
    updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_object_status ON meta_objects(status);
CREATE INDEX IF NOT EXISTS idx_object_type ON meta_objects(object_type);
CREATE INDEX IF NOT EXISTS idx_prop_object ON meta_properties(object_id);
CREATE INDEX IF NOT EXISTS idx_prop_semantic ON meta_properties(semantic_type);
CREATE INDEX IF NOT EXISTS idx_relation_source ON meta_relations(source_object_id);
CREATE INDEX IF NOT EXISTS idx_relation_target ON meta_relations(target_object_id);
CREATE INDEX IF NOT EXISTS idx_event_object ON meta_events(object_id);
CREATE INDEX IF NOT EXISTS idx_event_timestamp ON meta_events(timestamp);
"""
