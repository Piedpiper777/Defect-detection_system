import json
import os
import csv
from typing import Dict, Any

SCHEMA_FILE = os.getenv(
    "KG_SCHEMA_FILE",
    os.path.join(os.path.dirname(__file__), "schema.json")
)
DEFAULT_IMPORT_DIR = os.getenv(
    "KG_IMPORT_DIR",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "neo4j-community-5.26.18", "import"))
)

FALLBACK_SCHEMA = {
    'labels': [
        {'label': 'DetectObject', 'properties': {'name': {}}},
        {'label': 'DefectType', 'properties': {'name': {}}},
        {'label': 'Cause', 'properties': {'name': {}}},
        {'label': 'Solution', 'properties': {'name': {}}},
    ],
    'relationship_types': [
        {'type': '有缺陷', 'properties': {}},
        {'type': '导致', 'properties': {}},
        {'type': '解决', 'properties': {}},
    ]
}


def _normalize_label(raw: str) -> str:
    if raw is None:
        return ""
    return raw.strip()


def load_schema() -> Dict[str, Any]:
    if not os.path.exists(SCHEMA_FILE):
        return {}
    try:
        with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_schema(schema: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(SCHEMA_FILE), exist_ok=True)
    with open(SCHEMA_FILE, "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)


def _parse_node_csv(path: str):
    labels = {}
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return {}
        id_fields = [c for c in reader.fieldnames if ":ID" in c]
        label_field = next((c for c in reader.fieldnames if c.startswith(":LABEL") or c == ":LABEL"), None)
        for row in reader:
            # Determine label
            label_val = None
            if label_field:
                label_val = row.get(label_field)
            elif id_fields:
                # get label from :ID(Type)
                parts = id_fields[0].split("(")
                if len(parts) > 1 and parts[1].endswith(")"):
                    label_val = parts[1][:-1]
            label = _normalize_label(label_val) or "Node"
            labels.setdefault(label, set())
            for k, v in row.items():
                if k in id_fields or k == label_field:
                    continue
                if k:
                    labels[label].add(k)
    return {lbl: sorted(list(props)) for lbl, props in labels.items()}


def _parse_rel_csv(path: str):
    rels = {}
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return {}
        type_field = next((c for c in reader.fieldnames if c.startswith(":TYPE") or c == ":TYPE"), None)
        start_field = next((c for c in reader.fieldnames if ":START_ID" in c), None)
        end_field = next((c for c in reader.fieldnames if ":END_ID" in c), None)
        for row in reader:
            rel_type = _normalize_label(row.get(type_field)) if type_field else ""
            if not rel_type:
                continue
            rels.setdefault(rel_type, set())
            for k, v in row.items():
                if k in (type_field, start_field, end_field):
                    continue
                if k:
                    rels[rel_type].add(k)
    return {rtype: sorted(list(props)) for rtype, props in rels.items()}


def generate_schema_from_import(import_dir: str = None) -> Dict[str, Any]:
    base = import_dir or DEFAULT_IMPORT_DIR
    if not os.path.isdir(base):
        raise FileNotFoundError(f"Import 目录不存在: {base}")

    labels = {}
    rels = {}
    for fname in os.listdir(base):
        path = os.path.join(base, fname)
        if not os.path.isfile(path) or not fname.lower().endswith(".csv"):
            continue
        try:
            if fname.startswith("node_"):
                node_props = _parse_node_csv(path)
                for lbl, props in node_props.items():
                    labels.setdefault(lbl, set()).update(props)
            elif fname.startswith("rel_"):
                rel_props = _parse_rel_csv(path)
                for rtype, props in rel_props.items():
                    rels.setdefault(rtype, set()).update(props)
        except Exception:
            # skip problematic files but continue
            continue

    schema = {
        "labels": [
            {"label": lbl, "properties": {p: {} for p in sorted(props)}}
            for lbl, props in labels.items()
        ],
        "relationship_types": [
            {"type": rtype, "properties": {p: {} for p in sorted(props)}}
            for rtype, props in rels.items()
        ],
        "generated_from": base
    }
    save_schema(schema)
    return schema
