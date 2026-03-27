"""
Seed Ontology – Initialize KuzuDB with comprehensive entities and relationships

Provides seed data for geopolitics, technology/AI, and economy domains.
Uses idempotent MERGE patterns to prevent duplicates.

Coverage:
- **Geopolitics**: 60+ entities – international rivalries, sanctions, military alliances
- **Technology/AI**: 55+ entities – funding, models, energy consumption, job impact
- **Economy**: 50+ entities – trade, industry clusters, resource flows

Run with::

    python -m backend.knowledge_layer.seed_ontology

Key relationships seeded:
- US --strategic_rival--> Iran / China / Russia (strength 0.88-0.90)
- Israel --military_strike--> Iran / Lebanon / Hezbollah / Hamas
- Iran --controls--> Hezbollah / Lebanon / Strait_of_Hormuz
- North_Korea --alliance--> Russia / China
- US --sanctions--> Iran / Russia / North_Korea
- Taiwan --disputes--> China
- Ukraine --conflict--> Russia
- AI_startup --raises_funding_from--> Venture_Capital
- AI_model --causes--> job_displacement
- Data_Center --consumes--> Energy
- OpenSource_AI --democratizes--> AI_access
- Semiconductor --enables--> AI_advancement
- WTO --regulates--> International_Trade
- Silicon_Valley --hub_of--> Tech_Innovation
- Oil --flows_through--> Strait_of_Hormuz
- Tariff --impacts--> Trade_Volume
- Supply_Chain --vulnerable_to--> Geopolitical_Risk
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


def _ensure_backend_importable() -> None:
    """Add backend to sys.path if needed."""
    here = os.path.abspath(__file__)
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(here)))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)


# ---------------------------------------------------------------------------
# Seed data – entities
# Format: (name, type, description, virtue, role)
# ---------------------------------------------------------------------------

_ENTITIES: List[Tuple[str, str, str, Optional[str], Optional[str]]] = [

    # ── GEOPOLITICS: Nation-states ──────────────────────────────────────────
    ("US", "GPE", "United States of America – global superpower", "democratic order", "Global Hegemon"),
    ("China", "GPE", "People's Republic of China – rising superpower", "regional dominance", "Rising Power"),
    ("Russia", "GPE", "Russian Federation – revisionist power", "sovereignty assertion", "Revisionist State"),
    ("Iran", "GPE", "Islamic Republic of Iran – regional power", "anti-Western resistance", "Pariah State"),
    ("Israel", "GPE", "State of Israel – Middle East military power", "self-defense", "Regional Military Power"),
    ("Lebanon", "GPE", "Republic of Lebanon – fragile state", "sovereignty fragility", "Proxy Battleground"),
    ("North_Korea", "GPE", "Democratic People's Republic of Korea", "nuclear deterrence", "Rogue State"),
    ("Taiwan", "GPE", "Republic of China (Taiwan) – disputed territory", "democratic resilience", "Disputed Territory"),
    ("Ukraine", "GPE", "Ukraine – nation under invasion", "national survival", "Conflict Zone"),
    ("Belarus", "GPE", "Republic of Belarus – Russian ally", "regime stability", "Client State"),
    ("European_Union", "ORG", "Political and economic union of 27 European states", "multilateral cooperation", "Supranational Body"),
    ("UK", "GPE", "United Kingdom – post-Brexit global power", "rules-based order", "Middle Power"),
    ("France", "GPE", "French Republic – EU leader and nuclear power", "strategic autonomy", "EU Leader"),
    ("Germany", "GPE", "Federal Republic of Germany – economic powerhouse", "economic leadership", "EU Economic Engine"),
    ("Japan", "GPE", "Japan – US ally in Indo-Pacific", "pacifist constitutionalism", "US Indo-Pacific Ally"),
    ("South_Korea", "GPE", "Republic of Korea – US ally facing North Korea", "democratic resilience", "US Ally"),
    ("India", "GPE", "Republic of India – non-aligned emerging power", "strategic autonomy", "Swing State"),
    ("Saudi_Arabia", "GPE", "Kingdom of Saudi Arabia – oil power", "energy dominance", "Oil Power"),
    ("Turkey", "GPE", "Republic of Turkey – NATO member with dual alignment", "strategic ambiguity", "NATO Swing State"),
    ("Pakistan", "GPE", "Islamic Republic of Pakistan – China ally", "nuclear deterrence", "Regional Actor"),
    ("Syria", "GPE", "Syrian Arab Republic – conflict state", "regime survival", "Proxy State"),
    ("Iraq", "GPE", "Republic of Iraq – oil producer", "energy resources", "OPEC Member"),
    ("Yemen", "GPE", "Yemen – ongoing civil war zone", "humanitarian crisis", "Conflict Zone"),
    ("Venezuela", "GPE", "Bolivarian Republic of Venezuela – US-sanctioned", "anti-imperialism", "Sanctioned State"),
    ("Cuba", "GPE", "Republic of Cuba – US-sanctioned state", "revolutionary ideology", "Sanctioned State"),
    ("Myanmar", "GPE", "Myanmar – military junta", "authoritarian control", "Pariah State"),
    ("Serbia", "GPE", "Republic of Serbia – Russia-aligned Balkans state", "Slavic solidarity", "Russian Ally"),
    ("Hungary", "GPE", "Hungary – EU member with Russia ties", "sovereign democracy", "EU Outlier"),
    ("Poland", "GPE", "Republic of Poland – NATO front-line state", "NATO commitment", "Frontline NATO State"),
    ("Azerbaijan", "GPE", "Republic of Azerbaijan – energy corridor state", "energy leverage", "Regional Actor"),

    # ── GEOPOLITICS: Organizations ──────────────────────────────────────────
    ("NATO", "ORG", "North Atlantic Treaty Organization – Western military alliance", "collective defense", "Military Alliance"),
    ("UN", "ORG", "United Nations – global multilateral body", "global governance", "Multilateral Institution"),
    ("IAEA", "ORG", "International Atomic Energy Agency – nuclear watchdog", "non-proliferation", "Nuclear Watchdog"),
    ("OPEC", "ORG", "Organization of Petroleum Exporting Countries", "energy price control", "Energy Cartel"),
    ("SCO", "ORG", "Shanghai Cooperation Organisation – Eurasian security bloc", "anti-hegemony", "Eurasian Bloc"),
    ("Hezbollah", "ORG", "Lebanese militant group backed by Iran", "resistance ideology", "Iranian Proxy"),
    ("Hamas", "ORG", "Palestinian militant organization controlling Gaza", "Palestinian resistance", "Militant Organization"),
    ("Wagner_Group", "ORG", "Russian private military company", "force projection", "PMC"),
    ("ICC", "ORG", "International Criminal Court – war crimes tribunal", "international justice", "War Crimes Tribunal"),
    ("BRICS", "ORG", "Emerging market bloc: Brazil, Russia, India, China, South Africa", "multipolar order", "Emerging Market Bloc"),
    ("Houthi", "ORG", "Yemeni militant group backed by Iran", "anti-Western resistance", "Iranian Proxy"),

    # ── GEOPOLITICS: People ─────────────────────────────────────────────────
    ("Xi_Jinping", "PERSON", "General Secretary of Chinese Communist Party", "regional dominance", "CCP General Secretary"),
    ("Vladimir_Putin", "PERSON", "President of Russian Federation", "power consolidation", "President"),
    ("Kim_Jong_un", "PERSON", "Supreme Leader of North Korea", "nuclear deterrence", "Supreme Leader"),
    ("Benjamin_Netanyahu", "PERSON", "Prime Minister of Israel", "national security", "Prime Minister"),
    ("Joe_Biden", "PERSON", "46th President of the United States", "democratic order", "President"),
    ("Donald_Trump", "PERSON", "45th and 47th President of the United States", "America First", "President"),
    ("Volodymyr_Zelensky", "PERSON", "President of Ukraine", "national survival", "President"),
    ("Ayatollah_Khamenei", "PERSON", "Supreme Leader of Iran", "anti-Western resistance", "Supreme Leader"),

    # ── GEOPOLITICS: Concepts ───────────────────────────────────────────────
    ("Strait_of_Hormuz", "CONCEPT", "Critical oil shipping chokepoint – 20% world supply", "energy security", "Strategic Chokepoint"),
    ("Taiwan_Strait", "CONCEPT", "Contested waterway between China and Taiwan", "strategic tension", "Military Flashpoint"),
    ("South_China_Sea", "CONCEPT", "Disputed maritime territory in Southeast Asia", "territorial sovereignty", "Contested Waters"),
    ("Nuclear_Weapons", "CONCEPT", "Weapons of mass destruction using nuclear fission/fusion", "nuclear deterrence", "WMD"),
    ("Military_Alliance", "CONCEPT", "Formal mutual-defense pact between states", "collective security", "Security Architecture"),
    ("Geopolitical_Risk", "CONCEPT", "Risk arising from geopolitical instability", "risk assessment", "Risk Factor"),
    ("Cyber_Warfare", "CONCEPT", "State-sponsored attacks on digital infrastructure", "information dominance", "Asymmetric Weapon"),
    ("Disinformation", "CONCEPT", "Deliberate spread of false information", "information control", "Influence Operation"),
    ("Espionage", "CONCEPT", "State-sponsored intelligence gathering", "intelligence advantage", "Intelligence Tool"),
    ("Nuclear_Deterrence", "CONCEPT", "Prevention of attack through threat of nuclear response", "strategic stability", "Deterrence Strategy"),
    ("Sanctions", "CONCEPT", "Economic penalties imposed by states or organizations", "economic coercion", "Foreign Policy Tool"),

    # ── TECHNOLOGY / AI: Companies ──────────────────────────────────────────
    ("OpenAI", "ORG", "AI research laboratory – creator of GPT series", "AI safety", "AI Lab"),
    ("Google", "ORG", "Technology conglomerate – Alphabet subsidiary", "information organization", "Big Tech"),
    ("Microsoft", "ORG", "Technology corporation – major OpenAI investor", "enterprise productivity", "Big Tech"),
    ("Meta", "ORG", "Social media and AI company – Facebook parent", "social connectivity", "Big Tech"),
    ("Amazon", "ORG", "E-commerce and cloud computing giant – AWS", "customer obsession", "Big Tech"),
    ("Nvidia", "ORG", "GPU and AI chip manufacturer", "AI acceleration", "Chip Maker"),
    ("AMD", "ORG", "Advanced Micro Devices – GPU and CPU manufacturer", "computing performance", "Chip Maker"),
    ("TSMC", "ORG", "Taiwan Semiconductor Manufacturing Company – world leader", "precision manufacturing", "Chip Foundry"),
    ("Samsung", "ORG", "South Korean conglomerate – semiconductor and consumer electronics", "manufacturing excellence", "Chip Maker"),
    ("Intel", "ORG", "US semiconductor company – CPU and AI chip maker", "computing innovation", "Chip Maker"),
    ("Huawei", "ORG", "Chinese telecom and tech giant – US-sanctioned", "technological sovereignty", "Sanctioned Tech"),
    ("Baidu", "ORG", "Chinese AI and internet company", "AI development", "Chinese Big Tech"),
    ("Alibaba", "ORG", "Chinese e-commerce and cloud company", "digital economy", "Chinese Big Tech"),
    ("Tencent", "ORG", "Chinese internet and gaming conglomerate", "digital entertainment", "Chinese Big Tech"),
    ("ByteDance", "ORG", "Chinese tech company – TikTok parent", "content algorithms", "Chinese Big Tech"),
    ("Anthropic", "ORG", "AI safety company – creator of Claude", "AI safety", "AI Lab"),
    ("Mistral", "ORG", "European AI startup – open-weight LLM developer", "AI democratization", "AI Lab"),
    ("Tesla", "ORG", "Electric vehicle and AI company", "sustainable transport", "EV Maker"),
    ("SpaceX", "ORG", "Aerospace and satellite company – Starlink operator", "space innovation", "Aerospace"),
    ("Apple", "ORG", "Consumer electronics and AI company", "consumer privacy", "Big Tech"),
    ("DeepMind", "ORG", "AI research division of Google/Alphabet", "scientific AI", "AI Lab"),

    # ── TECHNOLOGY / AI: Venture Capital ────────────────────────────────────
    ("Venture_Capital", "CONCEPT", "Private equity funding for early-stage startups", "risk-taking innovation", "Funding Mechanism"),
    ("General_Catalyst", "ORG", "Venture capital firm – major AI investor", "innovation investment", "VC Firm"),
    ("Sequoia_Capital", "ORG", "Leading Silicon Valley venture capital firm", "startup ecosystem", "VC Firm"),
    ("SoftBank", "ORG", "Japanese tech investment conglomerate – Vision Fund", "tech bet", "Investment Fund"),
    ("Tiger_Global", "ORG", "Global technology-focused hedge fund", "growth investing", "Investment Fund"),

    # ── TECHNOLOGY / AI: People ─────────────────────────────────────────────
    ("Sam_Altman", "PERSON", "CEO of OpenAI – AI industry leader", "AI safety and progress", "Tech CEO"),
    ("Jensen_Huang", "PERSON", "CEO and founder of Nvidia", "AI hardware vision", "Tech CEO"),
    ("Elon_Musk", "PERSON", "CEO of Tesla, SpaceX, and X – tech entrepreneur", "disruption", "Tech Entrepreneur"),
    ("Sundar_Pichai", "PERSON", "CEO of Google and Alphabet", "AI integration", "Tech CEO"),
    ("Satya_Nadella", "PERSON", "CEO of Microsoft", "cloud-first AI", "Tech CEO"),

    # ── TECHNOLOGY / AI: Concepts ───────────────────────────────────────────
    ("AI_model", "CONCEPT", "Trained machine learning system for inference", "intelligence augmentation", "AI Artifact"),
    ("AI_startup", "CONCEPT", "Early-stage company developing AI products", "innovation", "Startup"),
    ("AI_access", "CONCEPT", "Broad availability of AI tools and models", "democratization", "Access Resource"),
    ("GPU_chips", "CONCEPT", "Graphics processing units used for AI training", "compute power", "Hardware Resource"),
    ("Semiconductor", "CONCEPT", "Electronic chips enabling modern computing", "technological foundation", "Critical Component"),
    ("Data_Center", "CONCEPT", "Large facility housing computing infrastructure for AI", "compute infrastructure", "Infrastructure"),
    ("Energy", "CONCEPT", "Electrical power consumed by data centers and AI", "resource consumption", "Resource"),
    ("job_displacement", "CONCEPT", "Technological unemployment caused by AI automation", "social disruption", "Social Risk"),
    ("OpenSource_AI", "CONCEPT", "Publicly available AI models and tools", "open innovation", "Technology Enabler"),
    ("AI_advancement", "CONCEPT", "Progress in AI capabilities and applications", "technological progress", "Innovation Driver"),
    ("AI_safety", "CONCEPT", "Research and practices to ensure safe AI development", "responsible AI", "Safety Framework"),
    ("Large_Language_Model", "CONCEPT", "Large-scale neural network trained on text data", "language intelligence", "AI Model Type"),
    ("Cybersecurity", "CONCEPT", "Protection of digital systems from attacks", "digital defense", "Security Domain"),
    ("5G", "CONCEPT", "Fifth-generation wireless technology", "connectivity", "Telecom Standard"),
    ("Cloud_Computing", "CONCEPT", "On-demand delivery of computing resources via internet", "scalability", "Platform"),
    ("Quantum_Computing", "CONCEPT", "Computing using quantum mechanical phenomena", "next-gen compute", "Emerging Technology"),
    ("Tech_Company", "CONCEPT", "Company primarily operating in technology sector", "digital innovation", "Market Actor"),
    ("Digital_Transformation", "CONCEPT", "Adoption of digital technologies across industries", "modernization", "Business Process"),
    ("Semiconductor_Supply_Chain", "CONCEPT", "Global network producing semiconductor chips", "strategic dependency", "Critical Supply Chain"),
    ("Renewable_Energy", "CONCEPT", "Energy from renewable sources – solar, wind, hydro", "clean energy", "Energy Source"),
    ("Electric_Vehicle", "CONCEPT", "Battery-powered automobile", "clean transport", "Green Technology"),
    ("Blockchain", "CONCEPT", "Distributed ledger technology", "decentralization", "Technology Protocol"),
    ("Cryptocurrency", "CONCEPT", "Digital currency using cryptography", "financial disruption", "Digital Asset"),
    ("Autonomous_Vehicles", "CONCEPT", "Self-driving vehicle technology", "mobility innovation", "Emerging Technology"),
    ("Worker_Transition_Fund", "CONCEPT", "Policy mechanism funding AI job displacement mitigation", "social equity", "Policy Tool"),

    # ── ECONOMY: Organizations ──────────────────────────────────────────────
    ("WTO", "ORG", "World Trade Organization – global trade regulator", "free trade", "Trade Regulator"),
    ("IMF", "ORG", "International Monetary Fund – global financial stabilizer", "financial stability", "Financial Institution"),
    ("World_Bank", "ORG", "International development finance institution", "development finance", "Development Institution"),
    ("Federal_Reserve", "ORG", "US central bank – monetary policy authority", "price stability", "Central Bank"),
    ("ECB", "ORG", "European Central Bank – Eurozone monetary authority", "Eurozone stability", "Central Bank"),
    ("SWIFT", "ORG", "Society for Worldwide Interbank Financial Telecommunication", "financial messaging", "Financial Infrastructure"),
    ("G7", "ORG", "Group of Seven major advanced economies", "Western economic coordination", "Economic Forum"),
    ("G20", "ORG", "Group of Twenty major economies", "global economic coordination", "Economic Forum"),
    ("ASEAN", "ORG", "Association of Southeast Asian Nations", "regional integration", "Regional Bloc"),

    # ── ECONOMY: People ─────────────────────────────────────────────────────
    ("Janet_Yellen", "PERSON", "US Treasury Secretary – former Fed Chair", "financial stability", "Treasury Secretary"),
    ("Jerome_Powell", "PERSON", "Chair of the Federal Reserve", "price stability", "Central Bank Chair"),
    ("Christine_Lagarde", "PERSON", "President of the European Central Bank", "Eurozone stability", "Central Bank President"),

    # ── ECONOMY: Concepts ───────────────────────────────────────────────────
    ("International_Trade", "CONCEPT", "Exchange of goods and services across national borders", "economic interdependence", "Economic Activity"),
    ("Trade_Volume", "CONCEPT", "Total amount of goods traded globally", "economic growth indicator", "Economic Metric"),
    ("Tariff", "CONCEPT", "Tax on imports/exports – trade protection tool", "economic protectionism", "Trade Policy"),
    ("Supply_Chain", "CONCEPT", "Network of producers delivering goods to consumers", "economic efficiency", "Production Network"),
    ("Oil", "CONCEPT", "Crude petroleum – primary global energy commodity", "energy security", "Strategic Commodity"),
    ("Natural_Gas", "CONCEPT", "Gaseous fossil fuel used for heating and power", "energy dependency", "Strategic Commodity"),
    ("Silicon_Valley", "CONCEPT", "US tech industry hub – San Francisco Bay Area", "tech innovation", "Innovation Hub"),
    ("Tech_Innovation", "CONCEPT", "Breakthrough technological development", "economic progress", "Innovation Driver"),
    ("Inflation", "CONCEPT", "Rise in general price level of goods and services", "economic stability", "Economic Metric"),
    ("Interest_Rates", "CONCEPT", "Cost of borrowing set by central banks", "monetary policy", "Policy Lever"),
    ("US_Dollar", "CONCEPT", "Primary global reserve currency", "dollar hegemony", "Reserve Currency"),
    ("Yuan", "CONCEPT", "Chinese renminbi – currency of China", "currency internationalization", "Emerging Reserve Currency"),
    ("Trade_War", "CONCEPT", "Escalating tariff conflict between major economies", "economic nationalism", "Economic Conflict"),
    ("Belt_and_Road", "CONCEPT", "China's global infrastructure investment initiative", "economic influence", "China Initiative"),
    ("CHIPS_Act", "CONCEPT", "US law subsidizing domestic semiconductor manufacturing", "tech sovereignty", "Industrial Policy"),
    ("Rare_Earth_Metals", "CONCEPT", "Critical minerals for technology manufacturing", "resource control", "Strategic Resource"),
    ("Manufacturing", "CONCEPT", "Industrial production of goods", "economic output", "Economic Sector"),
    ("Foreign_Direct_Investment", "CONCEPT", "Cross-border investment in business operations", "capital flows", "Investment Mechanism"),
    ("Economic_Sanctions", "CONCEPT", "Economic penalties imposed to change state behavior", "coercive diplomacy", "Foreign Policy Tool"),
    ("Trade_Deficit", "CONCEPT", "Negative trade balance – imports exceed exports", "economic imbalance", "Economic Metric"),
    ("Inflation_Reduction_Act", "CONCEPT", "US legislation on climate, healthcare, and tax policy", "green transition", "US Industrial Policy"),
    ("Carbon_Tariff", "CONCEPT", "Tariff on imports based on carbon footprint", "climate protection", "Climate Policy"),
    ("Energy_Security", "CONCEPT", "Reliable access to affordable energy resources", "strategic resilience", "National Priority"),
    ("LNG", "CONCEPT", "Liquefied natural gas – transportable energy commodity", "energy diversification", "Energy Commodity"),
    ("Financial_Market", "CONCEPT", "Markets for trading financial instruments", "capital allocation", "Economic Infrastructure"),
    ("Stock_Market", "CONCEPT", "Equity securities exchange", "investment vehicle", "Financial Market"),
    ("Bond_Market", "CONCEPT", "Debt securities market", "debt financing", "Financial Market"),
    ("Digital_Economy", "CONCEPT", "Economic activity enabled by digital technology", "digital growth", "Economic Sector"),
    ("Petrochemical", "CONCEPT", "Chemical products derived from petroleum", "industrial inputs", "Industrial Sector"),
]


# ---------------------------------------------------------------------------
# Seed data – relationships
# Format: (source, target, relation_type, strength)
# Note: target_virtue / target_role are stored on Entity nodes above
# ---------------------------------------------------------------------------

_RELATIONSHIPS: List[Tuple[str, str, str, float]] = [

    # ── GEOPOLITICS: US Strategic Rivalries ─────────────────────────────────
    ("US", "Iran", "strategic_rival", 0.90),
    ("US", "China", "strategic_rival", 0.88),
    ("US", "Russia", "strategic_rival", 0.88),
    ("US", "North_Korea", "strategic_rival", 0.85),

    # ── GEOPOLITICS: Israel Military Operations ──────────────────────────────
    ("Israel", "Iran", "military_strike", 0.90),
    ("Israel", "Lebanon", "military_strike", 0.85),
    ("Israel", "Hezbollah", "military_strike", 0.90),
    ("Israel", "Hamas", "military_strike", 0.92),

    # ── GEOPOLITICS: Iran Controls / Influence ───────────────────────────────
    ("Iran", "Hezbollah", "controls", 0.85),
    ("Iran", "Lebanon", "controls", 0.80),
    ("Iran", "Strait_of_Hormuz", "controls", 0.85),
    ("Iran", "Hamas", "supports", 0.80),
    ("Iran", "Houthi", "supports", 0.80),
    ("Iran", "Syria", "ally", 0.82),
    ("Iran", "Nuclear_Weapons", "develops", 0.75),

    # ── GEOPOLITICS: North Korea Alliances ───────────────────────────────────
    ("North_Korea", "Russia", "alliance", 0.90),
    ("North_Korea", "China", "alliance", 0.80),
    ("North_Korea", "Russia", "supplies_weapons", 0.85),
    ("North_Korea", "Nuclear_Weapons", "possesses", 0.95),
    ("North_Korea", "Cyber_Warfare", "conducts", 0.80),

    # ── GEOPOLITICS: US Sanctions ────────────────────────────────────────────
    ("US", "Iran", "sanctions", 0.90),
    ("US", "Russia", "sanctions", 0.88),
    ("US", "North_Korea", "sanctions", 0.85),
    ("US", "China", "sanctions", 0.70),
    ("US", "Venezuela", "sanctions", 0.80),
    ("US", "Cuba", "sanctions", 0.75),
    ("US", "Myanmar", "sanctions", 0.70),
    ("US", "Huawei", "sanctions", 0.90),
    ("US", "Belarus", "sanctions", 0.72),

    # ── GEOPOLITICS: Taiwan Disputes ─────────────────────────────────────────
    ("Taiwan", "China", "disputes", 0.90),
    ("China", "Taiwan", "claims", 0.92),
    ("China", "Taiwan_Strait", "militarizes", 0.88),
    ("China", "South_China_Sea", "claims", 0.90),
    ("US", "Taiwan", "defends", 0.82),
    ("Japan", "South_China_Sea", "disputes", 0.75),

    # ── GEOPOLITICS: Ukraine Conflict ────────────────────────────────────────
    ("Ukraine", "Russia", "conflict", 0.95),
    ("Russia", "Ukraine", "invades", 0.95),
    ("NATO", "Ukraine", "supports", 0.82),
    ("US", "Ukraine", "arms", 0.85),
    ("European_Union", "Ukraine", "supports", 0.85),

    # ── GEOPOLITICS: NATO Alliances ──────────────────────────────────────────
    ("NATO", "US", "includes", 0.95),
    ("NATO", "UK", "includes", 0.95),
    ("NATO", "France", "includes", 0.95),
    ("NATO", "Germany", "includes", 0.95),
    ("NATO", "Poland", "includes", 0.95),
    ("NATO", "Turkey", "includes", 0.85),
    ("NATO", "South_Korea", "partner", 0.80),
    ("NATO", "Japan", "partner", 0.80),
    ("US", "Israel", "ally", 0.92),
    ("US", "Japan", "ally", 0.90),
    ("US", "South_Korea", "ally", 0.90),
    ("US", "UK", "ally", 0.95),
    ("US", "European_Union", "ally", 0.85),
    ("US", "Saudi_Arabia", "ally", 0.78),
    ("US", "India", "partner", 0.75),

    # ── GEOPOLITICS: Russia Alliances ────────────────────────────────────────
    ("Russia", "China", "strategic_partner", 0.85),
    ("Russia", "Belarus", "controls", 0.80),
    ("Russia", "Syria", "ally", 0.85),
    ("Russia", "Iran", "ally", 0.80),
    ("Russia", "Venezuela", "ally", 0.70),
    ("Russia", "North_Korea", "alliance", 0.88),
    ("Belarus", "Russia", "ally", 0.92),

    # ── GEOPOLITICS: China Alliances ─────────────────────────────────────────
    ("China", "Russia", "strategic_partner", 0.85),
    ("China", "Pakistan", "ally", 0.82),
    ("China", "North_Korea", "ally", 0.78),
    ("China", "Myanmar", "ally", 0.80),
    ("China", "Serbia", "partner", 0.72),
    ("China", "Belt_and_Road", "leads", 0.92),
    ("China", "Rare_Earth_Metals", "controls", 0.88),
    ("China", "SCO", "leads", 0.88),
    ("India", "SCO", "member", 0.88),
    ("Russia", "SCO", "member", 0.95),
    ("Pakistan", "SCO", "member", 0.85),

    # ── GEOPOLITICS: Leadership ──────────────────────────────────────────────
    ("Xi_Jinping", "China", "leads", 0.98),
    ("Vladimir_Putin", "Russia", "leads", 0.98),
    ("Kim_Jong_un", "North_Korea", "leads", 0.98),
    ("Benjamin_Netanyahu", "Israel", "leads", 0.95),
    ("Joe_Biden", "US", "leads", 0.95),
    ("Donald_Trump", "US", "leads", 0.90),
    ("Volodymyr_Zelensky", "Ukraine", "leads", 0.95),
    ("Ayatollah_Khamenei", "Iran", "leads", 0.95),

    # ── GEOPOLITICS: Nuclear ─────────────────────────────────────────────────
    ("IAEA", "Iran", "inspects", 0.85),
    ("IAEA", "North_Korea", "sanctions_for_noncompliance", 0.80),
    ("Nuclear_Deterrence", "North_Korea", "strategy_of", 0.88),
    ("Nuclear_Deterrence", "Russia", "strategy_of", 0.85),
    ("Nuclear_Weapons", "Japan", "threatens", 0.80),
    ("Nuclear_Weapons", "South_Korea", "threatens", 0.80),
    ("Nuclear_Weapons", "Taiwan", "threatens", 0.75),

    # ── GEOPOLITICS: Energy Geopolitics ──────────────────────────────────────
    ("OPEC", "Oil", "controls", 0.90),
    ("OPEC", "Saudi_Arabia", "includes", 0.95),
    ("OPEC", "Iraq", "includes", 0.90),
    ("OPEC", "Venezuela", "includes", 0.80),
    ("Saudi_Arabia", "Iran", "rival", 0.85),
    ("Saudi_Arabia", "Oil", "exports", 0.95),
    ("Iran", "Oil", "exports", 0.80),
    ("Houthi", "Strait_of_Hormuz", "threatens", 0.70),
    ("Houthi", "Yemen", "controls", 0.80),
    ("Houthi", "Saudi_Arabia", "attacks", 0.78),
    ("Hezbollah", "Lebanon", "controls", 0.82),
    ("Hezbollah", "Israel", "attacks", 0.88),
    ("Hamas", "Israel", "attacks", 0.90),
    ("Wagner_Group", "Russia", "serves", 0.88),

    # ── GEOPOLITICS: Cyber and Information ────────────────────────────────────
    ("Russia", "Cyber_Warfare", "conducts", 0.82),
    ("China", "Cyber_Warfare", "conducts", 0.78),
    ("Russia", "Disinformation", "spreads", 0.85),
    ("China", "Disinformation", "spreads", 0.75),
    ("Iran", "Cyber_Warfare", "conducts", 0.72),
    ("Espionage", "US", "targets", 0.78),
    ("Espionage", "Taiwan", "targets", 0.78),
    ("Espionage", "Israel", "targets", 0.72),
    ("ICC", "Vladimir_Putin", "indicts", 0.85),
    ("ICC", "Russia", "investigates", 0.80),

    # ── GEOPOLITICS: UN Sanctions ─────────────────────────────────────────────
    ("UN", "North_Korea", "sanctions", 0.85),
    ("UN", "Russia", "sanctions", 0.72),
    ("UN", "Iran", "sanctions", 0.78),
    ("G7", "Russia", "sanctions", 0.92),
    ("European_Union", "Russia", "sanctions", 0.88),
    ("BRICS", "China", "led_by", 0.90),
    ("BRICS", "Russia", "includes", 0.88),
    ("BRICS", "India", "includes", 0.85),
    ("India", "Russia", "trade_partner", 0.72),
    ("India", "China", "rival", 0.80),
    ("India", "Pakistan", "rival", 0.85),

    # ── TECHNOLOGY / AI: Funding ─────────────────────────────────────────────
    ("AI_startup", "Venture_Capital", "raises_funding_from", 0.85),
    ("AI_startup", "General_Catalyst", "raises_funding_from", 0.82),
    ("AI_startup", "Sequoia_Capital", "raises_funding_from", 0.80),
    ("AI_startup", "SoftBank", "raises_funding_from", 0.78),
    ("AI_startup", "Tiger_Global", "raises_funding_from", 0.75),
    ("Venture_Capital", "AI_startup", "invests_in", 0.85),
    ("General_Catalyst", "AI_startup", "invests_in", 0.82),
    ("Sequoia_Capital", "AI_startup", "invests_in", 0.80),
    ("SoftBank", "AI_startup", "invests_in", 0.78),
    ("Tiger_Global", "AI_startup", "invests_in", 0.75),
    ("OpenAI", "Venture_Capital", "raises_funding_from", 0.82),
    ("Anthropic", "Venture_Capital", "raises_funding_from", 0.80),
    ("Mistral", "Venture_Capital", "raises_funding_from", 0.78),

    # ── TECHNOLOGY / AI: AI Model Causality ──────────────────────────────────
    ("AI_model", "job_displacement", "causes", 0.80),
    ("AI_model", "AI_advancement", "enables", 0.90),
    ("AI_model", "Data_Center", "requires", 0.88),
    ("AI_model", "GPU_chips", "requires", 0.90),
    ("AI_model", "Energy", "consumes", 0.82),
    ("AI_model", "Disinformation", "generates", 0.78),
    ("AI_model", "AI_safety", "demands", 0.80),
    ("AI_model", "Espionage", "enables", 0.72),
    ("Large_Language_Model", "AI_model", "is_type_of", 0.95),
    ("Large_Language_Model", "AI_startup", "powers", 0.82),
    ("AI_advancement", "job_displacement", "threatens", 0.80),
    ("AI_advancement", "Cybersecurity", "challenges", 0.75),

    # ── TECHNOLOGY / AI: Data Center & Energy ─────────────────────────────────
    ("Data_Center", "Energy", "consumes", 0.90),
    ("Data_Center", "GPU_chips", "requires", 0.90),
    ("Data_Center", "Renewable_Energy", "transitions_to", 0.75),
    ("Data_Center", "US", "located_in", 0.72),
    ("Data_Center", "Cloud_Computing", "enables", 0.88),

    # ── TECHNOLOGY / AI: Open Source & Access ─────────────────────────────────
    ("OpenSource_AI", "AI_access", "democratizes", 0.80),
    ("OpenSource_AI", "Venture_Capital", "disrupts", 0.72),
    ("OpenSource_AI", "AI_model", "releases", 0.85),
    ("AI_access", "Digital_Transformation", "enables", 0.80),

    # ── TECHNOLOGY / AI: Hardware Chain ───────────────────────────────────────
    ("Tech_Company", "GPU_chips", "uses", 0.85),
    ("Tech_Company", "AI_model", "invests_in", 0.90),
    ("Tech_Company", "Cloud_Computing", "provides", 0.88),
    ("Semiconductor", "AI_advancement", "enables", 0.90),
    ("Semiconductor", "GPU_chips", "enables", 0.88),
    ("GPU_chips", "Data_Center", "powers", 0.90),
    ("GPU_chips", "AI_model", "enables", 0.88),
    ("Nvidia", "GPU_chips", "produces", 0.95),
    ("AMD", "GPU_chips", "produces", 0.88),
    ("TSMC", "Semiconductor", "manufactures", 0.95),
    ("Samsung", "Semiconductor", "manufactures", 0.90),
    ("Intel", "Semiconductor", "manufactures", 0.85),
    ("CHIPS_Act", "Semiconductor", "subsidizes", 0.90),
    ("CHIPS_Act", "Semiconductor_Supply_Chain", "strengthens", 0.88),
    ("Semiconductor_Supply_Chain", "TSMC", "depends_on", 0.92),
    ("Semiconductor_Supply_Chain", "Taiwan", "depends_on", 0.90),
    ("China", "Semiconductor_Supply_Chain", "threatens", 0.85),
    ("US", "Semiconductor_Supply_Chain", "protects", 0.85),
    ("Rare_Earth_Metals", "Semiconductor", "required_for", 0.90),

    # ── TECHNOLOGY / AI: Company Profiles ─────────────────────────────────────
    ("OpenAI", "AI_model", "develops", 0.95),
    ("OpenAI", "Sam_Altman", "led_by", 0.95),
    ("OpenAI", "Microsoft", "funded_by", 0.95),
    ("Anthropic", "AI_model", "develops", 0.90),
    ("Anthropic", "AI_safety", "prioritizes", 0.90),
    ("Mistral", "AI_model", "develops", 0.88),
    ("Mistral", "OpenSource_AI", "releases", 0.85),
    ("Mistral", "European_Union", "supported_by", 0.80),
    ("Google", "AI_model", "develops", 0.92),
    ("Google", "DeepMind", "owns", 0.98),
    ("Google", "Cloud_Computing", "provides", 0.92),
    ("Meta", "AI_model", "develops", 0.90),
    ("Meta", "OpenSource_AI", "releases", 0.88),
    ("Microsoft", "OpenAI", "invests_in", 0.95),
    ("Microsoft", "Cloud_Computing", "provides", 0.92),
    ("Amazon", "Cloud_Computing", "provides", 0.92),
    ("Amazon", "Data_Center", "operates", 0.90),
    ("Nvidia", "Jensen_Huang", "led_by", 0.95),
    ("Google", "Sundar_Pichai", "led_by", 0.95),
    ("Microsoft", "Satya_Nadella", "led_by", 0.95),
    ("Tesla", "Elon_Musk", "led_by", 0.90),
    ("SpaceX", "Elon_Musk", "led_by", 0.92),
    ("Sam_Altman", "OpenAI", "leads", 0.95),
    ("Jensen_Huang", "Nvidia", "leads", 0.95),
    ("Elon_Musk", "Tesla", "leads", 0.90),
    ("Elon_Musk", "SpaceX", "leads", 0.92),
    ("Sundar_Pichai", "Google", "leads", 0.95),
    ("Satya_Nadella", "Microsoft", "leads", 0.95),

    # ── TECHNOLOGY / AI: China Tech ───────────────────────────────────────────
    ("Huawei", "5G", "develops", 0.90),
    ("Huawei", "US", "sanctioned_by", 0.92),
    ("ByteDance", "AI_model", "develops", 0.80),
    ("Baidu", "AI_model", "develops", 0.85),
    ("Alibaba", "Cloud_Computing", "provides", 0.85),
    ("Tencent", "AI_startup", "invests_in", 0.80),
    ("China", "AI_model", "invests_in", 0.85),
    ("China", "Semiconductor", "develops", 0.80),
    ("US", "Huawei", "restricts", 0.92),
    ("US", "Semiconductor", "restricts_exports", 0.80),

    # ── TECHNOLOGY / AI: Green Tech ───────────────────────────────────────────
    ("Tesla", "Electric_Vehicle", "produces", 0.92),
    ("Electric_Vehicle", "Semiconductor", "requires", 0.85),
    ("Electric_Vehicle", "Oil", "competes_with", 0.75),
    ("Renewable_Energy", "Energy", "provides", 0.85),
    ("Energy", "Renewable_Energy", "transitioning_to", 0.78),
    ("Renewable_Energy", "Oil", "reduces_dependency_on", 0.72),
    ("Inflation_Reduction_Act", "Renewable_Energy", "supports", 0.88),
    ("Inflation_Reduction_Act", "Electric_Vehicle", "subsidizes", 0.82),

    # ── TECHNOLOGY / AI: Emerging Tech ────────────────────────────────────────
    ("Blockchain", "Cryptocurrency", "enables", 0.90),
    ("Cryptocurrency", "US_Dollar", "challenges", 0.72),
    ("Quantum_Computing", "Cybersecurity", "threatens", 0.75),
    ("5G", "Digital_Transformation", "enables", 0.85),
    ("Cloud_Computing", "AI_model", "enables", 0.88),
    ("Cybersecurity", "Digital_Transformation", "protects", 0.80),
    ("Cyber_Warfare", "Cybersecurity", "exploits", 0.82),
    ("AI_safety", "Sam_Altman", "championed_by", 0.75),
    ("job_displacement", "Worker_Transition_Fund", "justifies", 0.82),

    # ── ECONOMY: WTO and Trade Regulation ────────────────────────────────────
    ("WTO", "International_Trade", "regulates", 0.75),
    ("WTO", "US", "includes", 0.90),
    ("WTO", "China", "includes", 0.90),
    ("WTO", "European_Union", "includes", 0.90),
    ("WTO", "Tariff", "adjudicates", 0.78),

    # ── ECONOMY: Silicon Valley Hub ──────────────────────────────────────────
    ("Silicon_Valley", "Tech_Innovation", "hub_of", 0.90),
    ("Silicon_Valley", "AI_startup", "hub_of", 0.92),
    ("Silicon_Valley", "Venture_Capital", "hub_of", 0.88),
    ("Tech_Innovation", "Stock_Market", "drives", 0.75),
    ("Tech_Innovation", "Digital_Economy", "powers", 0.82),

    # ── ECONOMY: Oil and Energy Flows ────────────────────────────────────────
    ("Oil", "Strait_of_Hormuz", "flows_through", 0.85),
    ("Oil", "US_Dollar", "priced_in", 0.90),
    ("Oil", "Petrochemical", "feeds", 0.90),
    ("Oil", "Energy", "provides", 0.88),
    ("Natural_Gas", "Russia", "exported_by", 0.90),
    ("Natural_Gas", "European_Union", "imported_by", 0.82),
    ("Natural_Gas", "Energy", "provides", 0.85),
    ("LNG", "Natural_Gas", "replaces", 0.80),
    ("LNG", "US", "exported_by", 0.85),
    ("LNG", "European_Union", "imported_by", 0.85),
    ("Energy_Security", "Oil", "depends_on", 0.82),
    ("Energy_Security", "Natural_Gas", "depends_on", 0.80),
    ("Energy_Security", "Renewable_Energy", "strengthened_by", 0.80),
    ("Energy_Security", "Russia", "threatened_by", 0.80),
    ("OPEC", "Trade_Volume", "influences", 0.80),

    # ── ECONOMY: Tariffs and Trade Wars ──────────────────────────────────────
    ("Tariff", "Trade_Volume", "impacts", 0.80),
    ("Tariff", "Trade_War", "creates", 0.82),
    ("Trade_War", "International_Trade", "disrupts", 0.85),
    ("Trade_War", "US", "involves", 0.85),
    ("Trade_War", "China", "involves", 0.85),
    ("US", "Tariff", "imposes", 0.85),
    ("China", "Tariff", "imposes", 0.80),
    ("Carbon_Tariff", "International_Trade", "impacts", 0.75),
    ("Carbon_Tariff", "European_Union", "imposed_by", 0.75),

    # ── ECONOMY: Supply Chain ────────────────────────────────────────────────
    ("Supply_Chain", "Geopolitical_Risk", "vulnerable_to", 0.75),
    ("Supply_Chain", "Trade_War", "disrupted_by", 0.80),
    ("Supply_Chain", "China", "depends_on", 0.85),
    ("Supply_Chain", "Manufacturing", "depends_on", 0.88),
    ("International_Trade", "Supply_Chain", "depends_on", 0.85),
    ("Manufacturing", "Supply_Chain", "part_of", 0.88),
    ("Manufacturing", "China", "located_in", 0.85),
    ("Manufacturing", "India", "emerging_hub", 0.75),
    ("Manufacturing", "Energy", "requires", 0.82),
    ("Semiconductor_Supply_Chain", "Supply_Chain", "is_part_of", 0.88),
    ("Semiconductor_Supply_Chain", "Trade_War", "disrupted_by", 0.80),

    # ── ECONOMY: Monetary Policy ─────────────────────────────────────────────
    ("Federal_Reserve", "Interest_Rates", "controls", 0.95),
    ("ECB", "Interest_Rates", "controls", 0.92),
    ("Interest_Rates", "Inflation", "controls", 0.85),
    ("Interest_Rates", "Stock_Market", "affects", 0.82),
    ("Interest_Rates", "Bond_Market", "affects", 0.80),
    ("Interest_Rates", "Financial_Market", "affects", 0.85),
    ("Inflation", "Interest_Rates", "drives", 0.82),
    ("Inflation", "Trade_Volume", "reduces", 0.72),
    ("Jerome_Powell", "Federal_Reserve", "leads", 0.95),
    ("Janet_Yellen", "Federal_Reserve", "formerly_led", 0.88),
    ("Christine_Lagarde", "ECB", "leads", 0.95),
    ("IMF", "Inflation", "monitors", 0.85),
    ("IMF", "Ukraine", "lends_to", 0.80),
    ("World_Bank", "Manufacturing", "funds", 0.75),

    # ── ECONOMY: Reserve Currency & Finance ──────────────────────────────────
    ("US_Dollar", "International_Trade", "dominates", 0.88),
    ("US_Dollar", "SWIFT", "used_in", 0.92),
    ("Yuan", "US_Dollar", "challenges", 0.70),
    ("BRICS", "Yuan", "promotes", 0.75),
    ("BRICS", "US_Dollar", "challenges", 0.72),
    ("Cryptocurrency", "US_Dollar", "challenges", 0.72),
    ("SWIFT", "International_Trade", "facilitates", 0.85),
    ("SWIFT", "Russia", "excludes", 0.88),
    ("SWIFT", "Financial_Market", "dominates", 0.82),

    # ── ECONOMY: G7/G20 ──────────────────────────────────────────────────────
    ("G7", "US", "includes", 0.95),
    ("G7", "UK", "includes", 0.95),
    ("G7", "France", "includes", 0.95),
    ("G7", "Germany", "includes", 0.95),
    ("G7", "Japan", "includes", 0.95),
    ("G7", "Russia", "sanctions", 0.92),
    ("G20", "China", "includes", 0.90),
    ("G20", "India", "includes", 0.85),
    ("G20", "Russia", "includes", 0.85),
    ("G20", "International_Trade", "coordinates", 0.78),

    # ── ECONOMY: Economic Sanctions ──────────────────────────────────────────
    ("Economic_Sanctions", "Russia", "targets", 0.90),
    ("Economic_Sanctions", "Iran", "targets", 0.88),
    ("Economic_Sanctions", "US", "imposed_by", 0.90),
    ("Economic_Sanctions", "European_Union", "imposed_by", 0.85),
    ("Economic_Sanctions", "Trade_Volume", "reduces", 0.80),
    ("Sanctions", "Russia", "hurts", 0.85),
    ("Sanctions", "Iran", "restricts", 0.88),
    ("Sanctions", "North_Korea", "restricts", 0.85),

    # ── ECONOMY: Investment and Development ──────────────────────────────────
    ("Foreign_Direct_Investment", "China", "flows_to", 0.80),
    ("Foreign_Direct_Investment", "India", "flows_to", 0.75),
    ("Belt_and_Road", "International_Trade", "expands", 0.80),
    ("Belt_and_Road", "US", "rivals", 0.72),
    ("Trade_Deficit", "US", "experienced_by", 0.80),
    ("Trade_Deficit", "China", "caused_by", 0.75),

    # ── ECONOMY: Digital Economy ──────────────────────────────────────────────
    ("Digital_Economy", "International_Trade", "transforms", 0.78),
    ("Digital_Economy", "Tech_Innovation", "driven_by", 0.85),
    ("Financial_Market", "Geopolitical_Risk", "affected_by", 0.78),
    ("Financial_Market", "Interest_Rates", "sensitive_to", 0.85),
    ("Stock_Market", "Tech_Innovation", "reflects", 0.75),
    ("Bond_Market", "Inflation", "sensitive_to", 0.80),
    ("ASEAN", "International_Trade", "promotes", 0.80),
    ("ASEAN", "Supply_Chain", "diversifies", 0.75),
]


class SeedOntologySeeder:
    """Seeds comprehensive ontological data into KuzuDB.

    Covers geopolitics, technology/AI, and economy domains with 150+ entities
    and 300+ relationships. Uses the same KuzuDB connection pattern as
    KuzuContextExtractor. All insertions are idempotent via MERGE.
    """

    def __init__(self, db_path: str = "./data/kuzu_db.db") -> None:
        """Initialize seeder with KuzuDB connection."""
        try:
            import kuzu  # type: ignore
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            self._db = kuzu.Database(db_path)
            self._conn = kuzu.Connection(self._db)
            self._available = True
        except ImportError:
            logger.error("kuzu package not installed")
            self._available = False
            self._conn = None
        except Exception as exc:
            logger.error("Failed to connect to KuzuDB: %s", exc)
            self._available = False
            self._conn = None

        self.entities_created = 0
        self.relationships_created = 0

    def _ensure_schema(self) -> None:
        """Ensure basic schema exists (idempotent)."""
        if not self._available or not self._conn:
            return

        ddl_stmts = [
            "CREATE NODE TABLE IF NOT EXISTS Entity"
            "(name STRING PRIMARY KEY, type STRING, description STRING, virtue STRING, role STRING)",
            "CREATE REL TABLE IF NOT EXISTS RELATED"
            "(FROM Entity TO Entity, relation_type STRING, strength DOUBLE)",
        ]

        for stmt in ddl_stmts:
            try:
                self._conn.execute(stmt)
            except Exception as exc:
                logger.debug("Schema statement (idempotent): %s", exc)

    @staticmethod
    def _esc(value: str) -> str:
        """Escape a string for use in a Cypher string literal."""
        return value.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')

    def seed_entities(self) -> Tuple[int, List[str]]:
        """Seed all entities across three domains (idempotent MERGE).

        Returns:
            (count, list_of_entity_names)
        """
        if not self._available or not self._conn:
            logger.warning("KuzuDB not available; skipping entity seeding")
            return 0, []

        count = 0
        names: List[str] = []

        for name, etype, desc, virtue, role in _ENTITIES:
            names.append(name)
            try:
                virtue_val = f"'{self._esc(virtue)}'" if virtue else "null"
                role_val = f"'{self._esc(role)}'" if role else "null"
                query = (
                    f"MERGE (e:Entity {{name: '{self._esc(name)}'}}) "
                    f"ON CREATE SET "
                    f"e.type = '{self._esc(etype)}', "
                    f"e.description = '{self._esc(desc)}', "
                    f"e.virtue = {virtue_val}, "
                    f"e.role = {role_val} "
                    f"RETURN e.name"
                )
                result = self._conn.execute(query)
                if result.has_next():
                    count += 1
                    logger.debug("Seeded entity: %s", name)
            except Exception as exc:
                logger.debug("Entity seed (may be duplicate): %s – %s", name, exc)

        self.entities_created = count
        logger.info("Seeded %d entities", count)
        return count, names

    def seed_relationships(self, entity_names: Optional[List[str]] = None) -> int:  # noqa: ARG002
        """Seed all relationships across domains (idempotent MERGE).

        Args:
            entity_names: Deprecated – no longer used. Kept for backwards
                compatibility. All relationships from the module-level
                ``_RELATIONSHIPS`` list are inserted regardless of this value.

        Returns:
            Count of relationships created.
        """
        if not self._available or not self._conn:
            logger.warning("KuzuDB not available; skipping relationship seeding")
            return 0

        count = 0
        for source, target, rel_type, strength in _RELATIONSHIPS:
            try:
                query = (
                    f"MATCH (s:Entity {{name: '{self._esc(source)}'}}), "
                    f"(t:Entity {{name: '{self._esc(target)}'}}) "
                    f"MERGE (s)-[r:RELATED {{relation_type: '{self._esc(rel_type)}'}}]->(t) "
                    f"ON CREATE SET r.strength = {strength:.2f} "
                    f"RETURN r.relation_type"
                )
                result = self._conn.execute(query)
                if result.has_next():
                    count += 1
                    logger.debug(
                        "Seeded relationship: %s --%s--> %s (%.2f)",
                        source, rel_type, target, strength,
                    )
            except Exception as exc:
                logger.debug(
                    "Relationship seed (may be duplicate): %s -> %s – %s",
                    source, target, exc,
                )

        self.relationships_created = count
        logger.info("Seeded %d relationships", count)
        return count

    def seed_ontology(self) -> Tuple[int, int]:
        """Run full seeding pipeline.

        Returns:
            (entities_created, relationships_created)
        """
        if not self._available:
            logger.error("KuzuDB not available – cannot seed")
            return 0, 0

        logger.info("Starting ontology seeding…")
        self._ensure_schema()

        ent_count, entity_names = self.seed_entities()
        rel_count = self.seed_relationships(entity_names)

        logger.info(
            "✅ Ontology seeding complete: %d entities + %d relationships",
            ent_count,
            rel_count,
        )
        return ent_count, rel_count


def main() -> None:
    """Entry point for seed_ontology module."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    )

    _ensure_backend_importable()

    seeder = SeedOntologySeeder(db_path="./data/kuzu_db.db")
    if not seeder._available:
        logger.error("KuzuDB connection failed – cannot proceed")
        sys.exit(1)

    ent_count, rel_count = seeder.seed_ontology()

    print()
    print("=" * 70)
    print("🎯 SEED ONTOLOGY COMPLETE")
    print("=" * 70)
    print(f"Inserted {ent_count} nodes and {rel_count} relationships")
    print(f"⏰ Timestamp: {datetime.now().isoformat()}")
    print("=" * 70)


if __name__ == "__main__":
    main()