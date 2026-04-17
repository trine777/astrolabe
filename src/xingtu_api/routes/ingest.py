"""Ingest routes — file, Excel, database."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends

from ..deps import get_service, get_tenant

router = APIRouter()


@router.post("/ingest/file")
def ingest_file(
    file_path: str,
    collection_id: Optional[str] = None,
    tenant_id: str = Depends(get_tenant),
):
    service = get_service()
    result = service.ingest_file(file_path, collection_id, created_by="api")
    return result.model_dump()


@router.post("/ingest/excel")
def ingest_excel(
    file_path: str,
    collection_id: Optional[str] = None,
    sheet_name: Optional[str] = None,
    text_columns: Optional[list[str]] = None,
    tenant_id: str = Depends(get_tenant),
):
    service = get_service()
    result = service.ingest_excel(
        file_path, collection_id,
        sheet_name=sheet_name, text_columns=text_columns,
        created_by="api",
    )
    return result.model_dump()


@router.post("/ingest/database")
def ingest_database(
    connection_string: str,
    query: str,
    collection_id: Optional[str] = None,
    collection_name: Optional[str] = None,
    text_columns: Optional[list[str]] = None,
    tenant_id: str = Depends(get_tenant),
):
    service = get_service()
    result = service.ingest_database(
        connection_string, query, collection_id,
        collection_name=collection_name,
        text_columns=text_columns, created_by="api",
    )
    return result.model_dump()
