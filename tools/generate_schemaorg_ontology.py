import csv
import json
import os
from pathlib import Path

# Locate repo root relative to this script (tools/ is one level below root)
_REPO_ROOT = Path(__file__).resolve().parent.parent

# Input: schema.org CSV committed to backend/ontology/resources/
csv_path = _REPO_ROOT / "backend" / "ontology" / "resources" / "schemaorg-current-https-types.csv"

# Fallback to legacy data/ path if the above doesn't exist
if not csv_path.exists():
    csv_path = _REPO_ROOT / "data" / "raw" / "schemaorg-current-https-types.csv"

# Output: write to backend/ontology/resources/ (authoritative location)
output_path = _REPO_ROOT / "backend" / "ontology" / "resources" / "schemaorg_nodes.json"

# Ensure output directory exists
os.makedirs(output_path.parent, exist_ok=True)

if not csv_path.exists():
    raise FileNotFoundError(
        "schema.org CSV not found at "
        + str(csv_path)
        + ".\nDownload it from https://schema.org/version/latest/schemaorg-current-https-types.csv"
        " and place it at backend/ontology/resources/schemaorg-current-https-types.csv"
    )

core_nodes = {}

with open(csv_path, encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        type_label = row["label"]
        comment = row["comment"]
        type_id = row["id"]
        parent = row["subTypeOf"]
        core_nodes[type_label] = {
            "description": comment,
            "schema_url": type_id,
            "parent": parent
        }

with open(output_path, "w", encoding="utf-8") as out:
    json.dump(core_nodes, out, ensure_ascii=False, indent=2)

print(f"Export complete: {len(core_nodes)} node types written to {output_path}")
