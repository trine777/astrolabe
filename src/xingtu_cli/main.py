"""
星图 XingTu - CLI 工具

命令行界面，支持数据导入、搜索、集合管理、Agent 记忆等操作。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import click

from xingtu import XingTuService
from xingtu.config import XingTuConfig


def get_service() -> XingTuService:
    """获取 XingTuService 实例"""
    config = XingTuConfig.from_env()
    service = XingTuService(config)
    service.initialize()
    return service


def print_json(data, indent=2):
    """格式化输出 JSON"""
    click.echo(json.dumps(data, ensure_ascii=False, indent=indent, default=str))


@click.group()
@click.version_option(version="2.0.0", prog_name="xingtu")
def cli():
    """星图 XingTu - 多模态 Agent 数据库 CLI"""
    pass


# ===== 初始化 =====


@cli.command()
@click.option("--db-path", default="~/.xingtu/data", help="数据库路径")
def init(db_path: str):
    """初始化星图数据库"""
    config = XingTuConfig()
    config.store.db_path = db_path
    service = XingTuService(config)
    service.initialize()
    click.echo(f"星图数据库已初始化: {Path(db_path).expanduser()}")


# ===== 数据导入 =====


@cli.command()
@click.argument("source")
@click.option("--collection", "-c", default=None, help="目标集合 ID")
@click.option("--name", "-n", default=None, help="新集合名称")
@click.option("--type", "collection_type", default="documents", help="集合类型")
@click.option("--recursive", "-r", is_flag=True, default=True, help="递归导入目录")
def ingest(source: str, collection: Optional[str], name: Optional[str],
           collection_type: str, recursive: bool):
    """导入数据到星图

    SOURCE 可以是文件路径或目录路径。
    支持 CSV、JSON、PDF、TXT、图片等格式。
    """
    service = get_service()
    path = Path(source)

    if not path.exists():
        click.echo(f"错误: 路径不存在: {source}", err=True)
        sys.exit(1)

    # 如果指定了名称，先创建集合
    if name and not collection:
        col = service.create_collection(
            name=name, collection_type=collection_type, created_by="user"
        )
        collection = col["id"]
        click.echo(f"已创建集合: {name} ({collection})")

    if path.is_dir():
        result = service.ingest_directory(
            str(path), collection_id=collection, recursive=recursive, created_by="user"
        )
    else:
        result = service.ingest_file(str(path), collection_id=collection, created_by="user")

    click.echo(f"导入完成:")
    click.echo(f"  集合 ID: {result.collection_id}")
    click.echo(f"  添加文档: {result.documents_added}")
    if result.documents_failed > 0:
        click.echo(f"  失败文档: {result.documents_failed}")
    if result.errors:
        click.echo(f"  错误:")
        for err in result.errors[:5]:
            click.echo(f"    - {err}")


# ===== 搜索 =====


@cli.command()
@click.argument("query")
@click.option("--type", "search_type", default="hybrid",
              type=click.Choice(["vector", "text", "hybrid", "multimodal"]),
              help="搜索类型")
@click.option("--collection", "-c", default=None, help="限定集合 ID")
@click.option("--limit", "-l", default=10, help="返回数量")
@click.option("--json-output", "-j", is_flag=True, help="JSON 格式输出")
def search(query: str, search_type: str, collection: Optional[str],
           limit: int, json_output: bool):
    """搜索星图数据

    QUERY 为搜索查询文本。
    """
    service = get_service()
    results = service.search(
        query, search_type=search_type, collection_id=collection, limit=limit
    )

    if json_output:
        print_json(results)
    else:
        if not results:
            click.echo("未找到结果")
            return
        click.echo(f"找到 {len(results)} 个结果:\n")
        for i, r in enumerate(results, 1):
            score = r.get("score", 0)
            content = r.get("content", "")[:200]
            doc_id = r.get("id", "")[:8]
            click.echo(f"  {i}. [{score:.4f}] {content}")
            click.echo(f"     ID: {doc_id}...")
        click.echo()


# ===== 集合管理 =====


@cli.group()
def collections():
    """集合管理命令"""
    pass


@collections.command("list")
@click.option("--status", "-s", default=None, help="按状态过滤")
@click.option("--type", "collection_type", default=None, help="按类型过滤")
@click.option("--json-output", "-j", is_flag=True, help="JSON 格式输出")
def collections_list(status: Optional[str], collection_type: Optional[str],
                     json_output: bool):
    """列出所有集合"""
    service = get_service()
    results = service.list_collections(status=status, collection_type=collection_type)

    if json_output:
        cleaned = [{k: v for k, v in r.items() if not k.startswith("_")} for r in results]
        print_json(cleaned)
    else:
        if not results:
            click.echo("暂无集合")
            return
        click.echo(f"共 {len(results)} 个集合:\n")
        for r in results:
            name = r.get("name", "未命名")
            cid = r.get("id", "")[:8]
            ctype = r.get("collection_type", "")
            status_val = r.get("status", "")
            count = r.get("item_count", 0)
            click.echo(f"  [{cid}...] {name} ({ctype}) - {status_val} - {count} 项")


@collections.command("create")
@click.argument("name")
@click.option("--type", "collection_type", default="documents", help="集合类型")
@click.option("--description", "-d", default=None, help="集合描述")
def collections_create(name: str, collection_type: str, description: Optional[str]):
    """创建新集合"""
    service = get_service()
    result = service.create_collection(
        name=name, collection_type=collection_type,
        description=description, created_by="user"
    )
    click.echo(f"集合已创建: {result['name']} ({result['id']})")


@collections.command("delete")
@click.argument("collection_id")
@click.confirmation_option(prompt="确定要删除此集合及其所有文档吗?")
def collections_delete(collection_id: str):
    """删除集合"""
    service = get_service()
    service.delete_collection(collection_id)
    click.echo(f"集合已删除: {collection_id}")


# ===== Agent 记忆 =====


@cli.group()
def memory():
    """Agent 记忆管理"""
    pass


@memory.command("store")
@click.option("--agent", "-a", required=True, help="Agent ID")
@click.option("--content", "-c", required=True, help="记忆内容")
@click.option("--type", "memory_type", default="semantic", help="记忆类型")
@click.option("--importance", "-i", default=0.5, type=float, help="重要性 0-1")
def memory_store(agent: str, content: str, memory_type: str, importance: float):
    """存储 Agent 记忆"""
    service = get_service()
    result = service.store_memory(
        agent_id=agent, content=content,
        memory_type=memory_type, importance=importance,
    )
    click.echo(f"记忆已存储: {result['id']}")


@memory.command("recall")
@click.option("--agent", "-a", required=True, help="Agent ID")
@click.option("--query", "-q", required=True, help="检索查询")
@click.option("--type", "memory_type", default=None, help="记忆类型过滤")
@click.option("--limit", "-l", default=10, help="返回数量")
def memory_recall(agent: str, query: str, memory_type: Optional[str], limit: int):
    """检索 Agent 记忆"""
    service = get_service()
    results = service.recall_memories(
        agent_id=agent, query=query, memory_type=memory_type, limit=limit,
    )
    if not results:
        click.echo("未找到相关记忆")
        return
    click.echo(f"找到 {len(results)} 条记忆:\n")
    for i, r in enumerate(results, 1):
        content = r.get("content", "")[:200]
        score = r.get("score", 0)
        click.echo(f"  {i}. [{score:.4f}] {content}")
        click.echo()


@memory.command("forget")
@click.option("--agent", "-a", required=True, help="Agent ID")
@click.option("--type", "memory_type", default=None, help="记忆类型（不指定则全部遗忘）")
@click.confirmation_option(prompt="确定要遗忘记忆吗?")
def memory_forget(agent: str, memory_type: Optional[str]):
    """遗忘 Agent 记忆"""
    service = get_service()
    service.forget_memories(agent_id=agent, memory_type=memory_type)
    click.echo(f"记忆已遗忘: agent={agent}, type={memory_type or 'all'}")


@memory.command("stats")
@click.option("--agent", "-a", required=True, help="Agent ID")
def memory_stats(agent: str):
    """查看 Agent 记忆统计"""
    service = get_service()
    result = service.get_memory_stats(agent)
    print_json(result)


# ===== 系统命令 =====


@cli.command()
def optimize():
    """优化星图数据库"""
    service = get_service()
    result = service.optimize()
    click.echo("数据库优化完成:")
    for table_name, info in result.items():
        status = info.get("status", "unknown")
        click.echo(f"  {table_name}: {status}")


@cli.command()
def stats():
    """查看系统统计"""
    service = get_service()
    result = service.get_stats()
    click.echo("星图系统统计:")
    for table_name, count in result.items():
        click.echo(f"  {table_name}: {count} 行")


@cli.command("world-model")
@click.option("--json-output", "-j", is_flag=True, help="JSON 格式输出")
def world_model(json_output: bool):
    """查看世界模型"""
    service = get_service()
    result = service.get_world_model()
    if json_output:
        print_json(result)
    else:
        click.echo("星图世界模型:")
        click.echo(f"  集合数: {result.get('collection_count', 0)}")
        click.echo(f"  文档数: {result.get('document_count', 0)}")
        click.echo(f"  关系数: {result.get('relation_count', 0)}")
        click.echo(f"  记忆数: {result.get('memory_count', 0)}")
        collections_data = result.get("collections", [])
        if collections_data:
            click.echo(f"\n  集合列表:")
            for c in collections_data:
                click.echo(f"    - {c.get('name', '未命名')} ({c.get('collection_type', '')})")


@cli.command()
@click.option("--target-id", default=None, help="按目标 ID 过滤")
@click.option("--type", "event_type", default=None, help="按事件类型过滤")
@click.option("--limit", "-l", default=20, help="返回数量")
def events(target_id: Optional[str], event_type: Optional[str], limit: int):
    """查看事件历史"""
    service = get_service()
    results = service.get_events(target_id=target_id, event_type=event_type, limit=limit)
    if not results:
        click.echo("暂无事件")
        return
    click.echo(f"最近 {len(results)} 个事件:\n")
    for e in results:
        ts = e.get("timestamp", "")[:19]
        etype = e.get("event_type", "")
        ttype = e.get("target_type", "")
        desc = e.get("description", "") or ""
        click.echo(f"  [{ts}] {etype} on {ttype}: {desc[:80]}")


if __name__ == "__main__":
    cli()
