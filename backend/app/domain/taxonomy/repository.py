"""Persistence adapters for taxonomy records."""

from __future__ import annotations

from datetime import datetime
from http import HTTPStatus
from threading import RLock
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Protocol

from sqlalchemy import (
    MetaData,
    Table,
    asc,
    delete,
    desc,
    func,
    insert,
    literal,
    select,
    update,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from ...infra.db import ENGINE
from ...infra.logging import get_logger
from .types import (
    TaxonomyKind,
    TaxonomyListResult,
    TaxonomyRow,
    TaxonomyServiceError,
    utcnow,
)

logger = get_logger(__name__)


class TaxonomyRepository(Protocol):  # pragma: no cover - interface only
    """Persistence abstraction consumed by :class:`TaxonomyService`."""

    def list(
        self,
        kind: TaxonomyKind,
        *,
        page: int,
        page_size: int,
        sort_by: str,
        sort_dir: str,
        active: bool | None,
        updated_after: datetime | None,
    ) -> TaxonomyListResult: ...

    def create(self, kind: TaxonomyKind, payload: Dict[str, Any]) -> TaxonomyRow: ...

    def update(
        self,
        kind: TaxonomyKind,
        *,
        taxonomy_id: str,
        payload: Dict[str, Any],
    ) -> TaxonomyRow: ...

    def delete(self, kind: TaxonomyKind, *, taxonomy_id: str) -> TaxonomyRow: ...

    def get(self, kind: TaxonomyKind, taxonomy_id: str) -> TaxonomyRow: ...


class InMemoryTaxonomyRepository(TaxonomyRepository):
    """In-memory adapter primarily used for tests."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._store: dict[TaxonomyKind, MutableMapping[str, TaxonomyRow]] = {
            TaxonomyKind.TYPE: {},
            TaxonomyKind.DOMAIN: {},
        }

    def list(
        self,
        kind: TaxonomyKind,
        *,
        page: int,
        page_size: int,
        sort_by: str,
        sort_dir: str,
        active: bool | None,
        updated_after: datetime | None,
    ) -> TaxonomyListResult:
        with self._lock:
            rows = list(self._store[kind].values())
        if active is not None:
            rows = [row for row in rows if row.active is active]
        if updated_after is not None:
            rows = [row for row in rows if row.updated_at > updated_after]

        rows = self._apply_sort(rows, sort_by, sort_dir)

        total = len(rows)
        start = (page - 1) * page_size
        end = start + page_size
        page_items = rows[start:end]
        last_cursor = max((row.updated_at for row in page_items), default=None)
        return TaxonomyListResult(
            items=page_items,
            page=page,
            page_size=page_size,
            total_items=total,
            last_updated_cursor=last_cursor,
        )

    def create(self, kind: TaxonomyKind, payload: Dict[str, Any]) -> TaxonomyRow:
        with self._lock:
            store = self._store[kind]
            if payload["id"] in store:
                raise _conflict(
                    kind,
                    message=f"{kind.value.title()} '{payload['id']}' already exists",
                    details={"id": payload["id"]},
                )
            self._ensure_unique_name_locked(store, payload["name"], None, kind)
            now = utcnow()
            row = TaxonomyRow(
                id=payload["id"],
                name=payload.get("name", payload["id"]),
                label=payload["label"],
                description=payload.get("description"),
                active=payload.get("active", True),
                sort_order=payload.get("sort_order", 500),
                metadata=dict(payload.get("metadata") or {}),
                created_at=now,
                updated_at=now,
            )
            store[row.id] = row
            return row

    def update(
        self,
        kind: TaxonomyKind,
        *,
        taxonomy_id: str,
        payload: Dict[str, Any],
    ) -> TaxonomyRow:
        with self._lock:
            store = self._store[kind]
            row = store.get(taxonomy_id)
            if row is None:
                raise _not_found(kind, taxonomy_id)
            if "name" in payload and payload["name"] is not None:
                self._ensure_unique_name_locked(
                    store,
                    payload["name"],
                    taxonomy_id,
                    kind,
                )
            updated = self._apply_updates(row, payload)
            store[taxonomy_id] = updated
            return updated

    def delete(self, kind: TaxonomyKind, *, taxonomy_id: str) -> TaxonomyRow:
        with self._lock:
            store = self._store[kind]
            row = store.pop(taxonomy_id, None)
            if row is None:
                raise _not_found(kind, taxonomy_id)
            return row

    def get(self, kind: TaxonomyKind, taxonomy_id: str) -> TaxonomyRow:
        with self._lock:
            row = self._store[kind].get(taxonomy_id)
            if row is None:
                raise _not_found(kind, taxonomy_id)
            return TaxonomyRow(**row.__dict__)

    @staticmethod
    def _apply_sort(
        rows: Iterable[TaxonomyRow], sort_by: str, sort_dir: str
    ) -> list[TaxonomyRow]:
        reverse = sort_dir.lower() == "desc"

        def sort_key(row: TaxonomyRow) -> Any:
            if sort_by == "label":
                return row.label.lower()
            if sort_by == "created_at":
                return row.created_at
            return (row.sort_order, row.label.lower())

        return sorted(rows, key=sort_key, reverse=reverse)

    @staticmethod
    def _ensure_unique_name_locked(
        store: MutableMapping[str, TaxonomyRow],
        name: str,
        exclude_id: str | None,
        kind: TaxonomyKind,
    ) -> None:
        canonical = name.casefold()
        for row_id, row in store.items():
            if exclude_id and row_id == exclude_id:
                continue
            if row.name.casefold() == canonical:
                raise _conflict(
                    kind,
                    message=f"Name '{name}' already exists",
                    details={"name": name},
                )

    @staticmethod
    def _apply_updates(row: TaxonomyRow, payload: Dict[str, Any]) -> TaxonomyRow:
        updated = TaxonomyRow(**row.__dict__)
        if "label" in payload and payload["label"] is not None:
            updated.label = payload["label"]
        if "name" in payload and payload["name"] is not None:
            updated.name = payload["name"]
        if "description" in payload:
            updated.description = payload["description"]
        if "sort_order" in payload and payload["sort_order"] is not None:
            updated.sort_order = payload["sort_order"]
        if "metadata" in payload and payload["metadata"] is not None:
            updated.metadata = payload["metadata"]
        if "active" in payload and payload["active"] is not None:
            updated.active = payload["active"]
        updated.updated_at = utcnow()
        return updated


class PostgresTaxonomyRepository(TaxonomyRepository):
    """SQLAlchemy-backed taxonomy adapter."""

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or ENGINE
        self._metadata = MetaData()
        self._tables: dict[TaxonomyKind, Table] = {
            TaxonomyKind.TYPE: Table(
                "entry_types", self._metadata, autoload_with=self._engine
            ),
            TaxonomyKind.DOMAIN: Table(
                "entry_domains", self._metadata, autoload_with=self._engine
            ),
        }
        self._entries = Table("entries", self._metadata, autoload_with=self._engine)
        self._type_fk = getattr(self._entries.c, "type_id", None)
        self._domain_fk = getattr(self._entries.c, "domain_id", None)

    def list(
        self,
        kind: TaxonomyKind,
        *,
        page: int,
        page_size: int,
        sort_by: str,
        sort_dir: str,
        active: bool | None,
        updated_after: datetime | None,
    ) -> TaxonomyListResult:
        table = self._tables[kind]
        conditions = []
        if active is not None:
            conditions.append(table.c.active.is_(active))
        if updated_after is not None:
            conditions.append(table.c.updated_at > updated_after)

        order_columns = self._order_columns(table, sort_by, sort_dir)
        ref_expr = self._referenced_entries_expr(kind, table)
        columns = [*table.c, ref_expr.label("referenced_entries")]

        stmt = select(*columns)
        if conditions:
            stmt = stmt.where(*conditions)
        stmt = stmt.order_by(*order_columns)
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        count_stmt = select(func.count()).select_from(table)
        if conditions:
            count_stmt = count_stmt.where(*conditions)

        with self._engine.begin() as conn:
            total = conn.execute(count_stmt).scalar_one()
            rows = conn.execute(stmt).mappings().all()

        taxonomy_rows = [self._row_from_mapping(row) for row in rows]
        last_cursor = max((row.updated_at for row in taxonomy_rows), default=None)
        return TaxonomyListResult(
            items=taxonomy_rows,
            page=page,
            page_size=page_size,
            total_items=total,
            last_updated_cursor=last_cursor,
        )

    def create(self, kind: TaxonomyKind, payload: Dict[str, Any]) -> TaxonomyRow:
        table = self._tables[kind]
        now = utcnow()
        values = self._coerce_payload(payload)
        values.setdefault("created_at", now)
        values.setdefault("updated_at", now)
        stmt = insert(table).values(**values).returning(table)
        with self._engine.begin() as conn:
            self._ensure_unique_name(conn, table, values["name"], None)
            try:
                row = conn.execute(stmt).mappings().first()
            except IntegrityError as exc:  # pragma: no cover - protective
                raise _conflict(
                    kind,
                    message=f"{kind.value.title()} '{values['id']}' already exists",
                    details={"id": values["id"]},
                ) from exc
            assert row is not None
            referenced = self._count_references(conn, kind, values["id"])
        row_dict = dict(row)
        row_dict["referenced_entries"] = referenced
        return self._row_from_mapping(row_dict)

    def update(
        self,
        kind: TaxonomyKind,
        *,
        taxonomy_id: str,
        payload: Dict[str, Any],
    ) -> TaxonomyRow:
        table = self._tables[kind]
        values = self._coerce_payload(payload)
        values["updated_at"] = utcnow()
        stmt = (
            update(table)
            .where(table.c.id == taxonomy_id)
            .values(**values)
            .returning(table)
        )
        with self._engine.begin() as conn:
            if "name" in values:
                self._ensure_unique_name(conn, table, values["name"], taxonomy_id)
            row = conn.execute(stmt).mappings().first()
            if row is None:
                raise _not_found(kind, taxonomy_id)
            referenced = self._count_references(conn, kind, taxonomy_id)
        row_dict = dict(row)
        row_dict["referenced_entries"] = referenced
        return self._row_from_mapping(row_dict)

    def delete(self, kind: TaxonomyKind, *, taxonomy_id: str) -> TaxonomyRow:
        table = self._tables[kind]
        with self._engine.begin() as conn:
            row = self._fetch_row(conn, table, taxonomy_id)
            if row is None:
                raise _not_found(kind, taxonomy_id)
            referenced = self._count_references(conn, kind, taxonomy_id)
            conn.execute(delete(table).where(table.c.id == taxonomy_id))
        row_dict = dict(row)
        row_dict["referenced_entries"] = referenced
        return self._row_from_mapping(row_dict)

    def get(self, kind: TaxonomyKind, taxonomy_id: str) -> TaxonomyRow:
        table = self._tables[kind]
        with self._engine.begin() as conn:
            row = self._fetch_row(conn, table, taxonomy_id)
            if row is None:
                raise _not_found(kind, taxonomy_id)
            referenced = self._count_references(conn, kind, taxonomy_id)
        row_dict = dict(row)
        row_dict["referenced_entries"] = referenced
        return self._row_from_mapping(row_dict)

    def _order_columns(self, table: Table, sort_by: str, sort_dir: str) -> list[Any]:
        direction = desc if sort_dir.lower() == "desc" else asc
        if sort_by == "label":
            return [direction(func.lower(table.c.label))]
        if sort_by == "created_at":
            return [direction(table.c.created_at)]
        # Default to sort_order then label for deterministic pagination
        return [
            direction(table.c.sort_order),
            direction(func.lower(table.c.label)),
        ]

    def _referenced_entries_expr(self, kind: TaxonomyKind, table: Table):
        fk_column = self._type_fk if kind is TaxonomyKind.TYPE else self._domain_fk
        if fk_column is None:
            return literal(0)
        return (
            select(func.count())
            .select_from(self._entries)
            .where(fk_column == table.c.id)
            .correlate(table)
            .scalar_subquery()
        )

    @staticmethod
    def _fetch_row(conn, table: Table, taxonomy_id: str):
        return (
            conn.execute(select(table).where(table.c.id == taxonomy_id))
            .mappings()
            .first()
        )

    @staticmethod
    def _coerce_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(payload)
        if "metadata" in data and data["metadata"] is not None:
            data["metadata"] = dict(data["metadata"])
        return data

    def _ensure_unique_name(
        self,
        conn,
        table: Table,
        name: str,
        exclude_id: str | None,
    ) -> None:
        stmt = select(table.c.id).where(func.lower(table.c.name) == name.casefold())
        if exclude_id:
            stmt = stmt.where(table.c.id != exclude_id)
        existing = conn.execute(stmt).first()
        if existing is not None:
            raise _conflict(
                TaxonomyKind.TYPE
                if table.name == "entry_types"
                else TaxonomyKind.DOMAIN,
                message=f"Name '{name}' already exists",
                details={"name": name},
            )

    def _count_references(
        self,
        conn,
        kind: TaxonomyKind,
        taxonomy_id: str,
    ) -> int:
        fk_column = self._type_fk if kind is TaxonomyKind.TYPE else self._domain_fk
        if fk_column is None:
            return 0
        stmt = (
            select(func.count())
            .select_from(self._entries)
            .where(fk_column == taxonomy_id)
        )
        return int(conn.execute(stmt).scalar_one())

    @staticmethod
    def _row_from_mapping(row: Mapping[str, Any]) -> TaxonomyRow:
        return TaxonomyRow(
            id=row["id"],
            name=row["name"],
            label=row["label"],
            description=row.get("description"),
            active=bool(row["active"]),
            sort_order=row["sort_order"],
            metadata=dict(row.get("metadata") or {}),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            referenced_entries=int(row.get("referenced_entries", 0) or 0),
        )


def _conflict(
    kind: TaxonomyKind, *, message: str, details: Dict[str, Any]
) -> TaxonomyServiceError:
    return TaxonomyServiceError(
        status_code=HTTPStatus.CONFLICT,
        error_code="EF07-CONFLICT",
        message=message,
        details=details,
    )


def _not_found(kind: TaxonomyKind, taxonomy_id: str) -> TaxonomyServiceError:
    return TaxonomyServiceError(
        status_code=HTTPStatus.NOT_FOUND,
        error_code="EF07-NOT-FOUND",
        message=f"{kind.value.title()} '{taxonomy_id}' not found",
        details={"id": taxonomy_id},
    )
