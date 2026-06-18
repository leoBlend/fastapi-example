"""
JSON-file DynamoDB simulator.

Implements the subset of boto3 DynamoDB Table methods used by the handlers:
  get_item, put_item, update_item, delete_item, query, scan

Each table is stored as a JSON file: {LOCAL_DATA_DIR}/{table_name}.json
Writes are atomic (write to .tmp then rename) to avoid corruption.

Supported key conditions for query():
  - KeyConditionExpression as a string like "PK = :pk" or "PK = :pk AND SK = :sk"
  - ExpressionAttributeValues dict
  - IndexName (GSI) — searches against the GSI PK/SK attributes instead of main PK

Supported filter for scan():
  - No filter — returns all items

Limitations (noted where relevant in handlers):
  - No DynamoDB Streams
  - No conditional expressions on put/delete
  - No transaction writes
"""
import json
import logging
import os
import pathlib
from typing import Any

logger = logging.getLogger(__name__)

_DATA_DIR = os.environ.get("LOCAL_DATA_DIR", "./aws/local_data")

# GSI definitions: table_name -> {index_name -> (pk_attr, sk_attr_or_None)}
_GSI_DEFS: dict[str, dict[str, tuple[str, str | None]]] = {
    "TodoApp-Users": {
        "EmailIndex": ("email", None),
        "UserIdIndex": ("user_id", None),
    },
    "TodoApp-Todos": {
        "OwnerIndex": ("owner_id", "created_at"),
    },
    "TodoApp-AuditLog": {
        "TimestampIndex": ("entity_type", "timestamp"),
    },
}


class LocalDynamoTable:
    def __init__(self, table_name: str):
        self._name = table_name
        self._path = pathlib.Path(_DATA_DIR) / f"{table_name}.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ load/save

    def _load(self) -> list[dict]:
        if not self._path.exists():
            return []
        with self._path.open() as f:
            return json.load(f).get("items", [])

    def _save(self, items: list[dict]) -> None:
        tmp = self._path.with_suffix(".tmp")
        with tmp.open("w") as f:
            json.dump({"items": items}, f, indent=2, default=str)
        tmp.replace(self._path)

    # ------------------------------------------------------------------ CRUD

    def get_item(self, Key: dict) -> dict:
        items = self._load()
        pk_attr, pk_val = next(iter(Key.items()))
        for item in items:
            if item.get(pk_attr) == pk_val:
                return {"Item": item}
        return {}

    def put_item(self, Item: dict) -> dict:
        items = self._load()
        # Replace if same PK exists
        pk_attr = list(Item.keys())[0]
        items = [i for i in items if i.get(pk_attr) != Item[pk_attr]]
        items.append(Item)
        self._save(items)
        return {}

    def update_item(self, Key: dict, UpdateExpression: str,
                    ExpressionAttributeValues: dict,
                    ExpressionAttributeNames: dict | None = None) -> dict:
        items = self._load()
        pk_attr, pk_val = next(iter(Key.items()))
        names = ExpressionAttributeNames or {}

        for item in items:
            if item.get(pk_attr) == pk_val:
                # Parse "SET #a = :a, #b = :b" — handles basic SET assignments
                expr = UpdateExpression.strip()
                if expr.upper().startswith("SET "):
                    expr = expr[4:]
                for assignment in expr.split(","):
                    lhs, rhs = assignment.strip().split("=")
                    attr = names.get(lhs.strip(), lhs.strip())
                    val_key = rhs.strip()
                    item[attr] = ExpressionAttributeValues[val_key]
                break
        self._save(items)
        return {}

    def delete_item(self, Key: dict) -> dict:
        items = self._load()
        pk_attr, pk_val = next(iter(Key.items()))
        updated = [i for i in items if i.get(pk_attr) != pk_val]
        self._save(updated)
        return {}

    def query(self, IndexName: str | None = None,
              KeyConditionExpression: str = "",
              ExpressionAttributeValues: dict | None = None,
              ScanIndexForward: bool = True) -> dict:
        """
        Parses simple "PK = :pk" and "PK = :pk AND SK = :sk" expressions.
        When IndexName is set, looks up the GSI definition to find which
        item attributes act as PK/SK.
        """
        vals = ExpressionAttributeValues or {}
        items = self._load()

        pk_attr, sk_attr = self._resolve_key_attrs(IndexName)
        pk_val, sk_val = self._parse_key_condition(KeyConditionExpression, vals)

        results = []
        for item in items:
            if item.get(pk_attr) != pk_val:
                continue
            if sk_val is not None and sk_attr and item.get(sk_attr) != sk_val:
                continue
            results.append(item)

        if sk_attr and sk_val is None:
            # Sort by SK when ranging over all SK values
            results.sort(key=lambda i: i.get(sk_attr, ""), reverse=not ScanIndexForward)

        return {"Items": results, "Count": len(results)}

    def scan(self) -> dict:
        items = self._load()
        return {"Items": items, "Count": len(items)}

    # ------------------------------------------------------------------ helpers

    def _resolve_key_attrs(self, index_name: str | None) -> tuple[str, str | None]:
        if index_name is None:
            return ("PK", None)
        gsi_map = _GSI_DEFS.get(self._name, {})
        if index_name not in gsi_map:
            raise ValueError(f"Unknown GSI '{index_name}' for table '{self._name}'")
        return gsi_map[index_name]

    def _parse_key_condition(self, expr: str, vals: dict) -> tuple[Any, Any]:
        """Returns (pk_value, sk_value_or_None)."""
        parts = [p.strip() for p in expr.upper().split(" AND ")]
        pk_placeholder = self._extract_placeholder(parts[0])
        pk_val = vals.get(pk_placeholder) if pk_placeholder else None
        sk_val = None
        if len(parts) > 1:
            sk_placeholder = self._extract_placeholder(parts[1])
            sk_val = vals.get(sk_placeholder) if sk_placeholder else None
        return pk_val, sk_val

    @staticmethod
    def _extract_placeholder(condition_part: str) -> str | None:
        # "PK = :pk"  →  ":pk" (case-insensitive match, return lowercase placeholder)
        tokens = condition_part.split("=")
        if len(tokens) == 2:
            return tokens[1].strip().lower()
        return None
