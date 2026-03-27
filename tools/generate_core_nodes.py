import json

# 用上述44个主类型（可精简/扩展）
core_types = [
    "Person", "Organization", "Corporation", "NGO", "GovernmentOrganization", "Project", "EducationalOrganization", "MedicalOrganization", "LocalBusiness",
    "Place", "Country", "City", "State", "AdministrativeArea", "GeoCoordinates", "LandmarksOrHistoricalBuildings", "Airport", "Facility",
    "NewsArticle", "Report", "DigitalDocument", "Message", "Dataset", "Website", "Blog", "Book", "SocialMediaPosting",
    "SoftwareApplication", "SoftwareSourceCode", "ComputerLanguage", "DataFeed", "Indicator", "APIReference", "Hardware", "CreativeWork", "WebPage", "Product", "Malware", "Event",
    "Action", "ControlAction", "AssessAction", "OrganizeAction", "SearchAction", "CreateAction", "CommunicateAction",
    "MonetaryAmount", "Status", "Role", "Observation", "StatisticalPopulation", "Review", "Rating", "Enumeration"
]

with open("data/schemaorg_nodes.json", encoding="utf-8") as f:
    nodes = json.load(f)

# 只保留需要的核心类
core_nodes = {typ: nodes[typ] for typ in core_types if typ in nodes}

# 可以生成为 ontology_subset.json（适配你初始化 KuzuDB 的逻辑）
ontology_subset = {
    "classes": core_nodes
}

with open("backend/config/ontology_subset.json", "w", encoding="utf-8") as out:
    json.dump(ontology_subset, out, ensure_ascii=False, indent=2)

print(f"✅ 导出核心本体类 {len(core_nodes)} 个 -> backend/config/ontology_subset.json")