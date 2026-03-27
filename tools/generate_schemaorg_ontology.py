import csv
import json

# 路径根据实际情况修改
csv_path = "data/raw/schemaorg-current-https-types.csv"
output_path = "data/schemaorg_nodes.json"

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

print(f"导出成功！共导出 {len(core_nodes)} 个节点类型到 {output_path}")