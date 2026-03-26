"""
Seed Ontology – Initialize KuzuDB with comprehensive entities and relationships

Provides seed data for geopolitics, technology/AI, and economy domains.
Uses idempotent MERGE patterns to prevent duplicates.

Run with::

    python -m backend.knowledge_layer.seed_ontology

Coverage:
- Geopolitics  (60+ entities): nation-states, alliances, leaders, conflicts
- Tech / AI    (55+ entities): companies, models, infrastructure, concepts
- Economy      (35+ entities): trade, energy, finance, supply-chain

Seeded example relationships:
- US --strategic_rival--> Iran (strength 0.90)
- Israel --military_strike--> Iran (strength 0.90)
- Iran --controls--> Strait_of_Hormuz (strength 0.90)
- North_Korea --alliance--> Russia (strength 0.85)
- AI_model --causes--> Job_Displacement (strength 0.85)
- Data_Center --consumes--> Energy (strength 0.90)
- OpenSource_AI --democratizes--> AI_Access (strength 0.80)
- WTO --regulates--> Trade (strength 0.90)
- Oil --flows_through--> Strait_of_Hormuz (strength 0.90)
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


def _ensure_backend_importable() -> None:
    """Add the repository root to sys.path if needed."""
    here = os.path.abspath(__file__)
    # navigate up: seed_ontology.py → knowledge_layer → backend → repo-root
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(here)))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _esc(text: str) -> str:
    """Escape a string for embedding inside a Cypher single-quoted literal."""
    return text.replace("\\", "\\\\").replace("'", "\\'")


# ---------------------------------------------------------------------------
# Seeder
# ---------------------------------------------------------------------------

class SeedOntologySeeder:
    """Seeds comprehensive ontological data into KuzuDB.

    Uses the same KuzuDB connection pattern as KuzuContextExtractor so that
    seeded data is immediately queryable by downstream intelligence modules.
    """

    def __init__(self, db_path: str = "./data/kuzu_db") -> None:
        """Open (or create) a KuzuDB database at *db_path*."""
        try:
            import kuzu  # type: ignore
            os.makedirs(db_path, exist_ok=True)
            self._db = kuzu.Database(db_path)
            self._conn = kuzu.Connection(self._db)
            self._available = True
        except ImportError:
            logger.error("kuzu package not installed – pip install kuzu")
            self._available = False
            self._conn = None
        except Exception as exc:
            logger.error("Failed to connect to KuzuDB at %s: %s", db_path, exc)
            self._available = False
            self._conn = None

        self.entities_created = 0
        self.relationships_created = 0

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_schema(self) -> None:
        """Create node/edge tables if they do not already exist (idempotent)."""
        if not self._available or not self._conn:
            return

        ddl_stmts = [
            (
                "CREATE NODE TABLE IF NOT EXISTS Entity"
                "(name STRING PRIMARY KEY, type STRING, description STRING,"
                " virtue STRING, role STRING)"
            ),
            (
                "CREATE REL TABLE IF NOT EXISTS RELATED"
                "(FROM Entity TO Entity,"
                " relation_type STRING, strength DOUBLE,"
                " virtue STRING, role STRING)"
            ),
        ]

        for stmt in ddl_stmts:
            try:
                self._conn.execute(stmt)
            except Exception as exc:
                logger.debug("Schema DDL (idempotent skip): %s", exc)

    # ------------------------------------------------------------------
    # Entity data
    # ------------------------------------------------------------------

    def _build_entities(self) -> List[Tuple[str, str, str, Optional[str], Optional[str]]]:
        """Return the master list of (name, type, description, virtue, role) tuples."""
        # fmt: off
        return [
            # ============================================================
            # GEOPOLITICS – Nation-states (30)
            # ============================================================
            ("US",           "GPE", "United States of America",           "liberal hegemony",      "Global Superpower"),
            ("Russia",       "GPE", "Russian Federation",                  "power consolidation",   "Major Power"),
            ("China",        "GPE", "People's Republic of China",          "regional dominance",    "Major Power"),
            ("Iran",         "GPE", "Islamic Republic of Iran",            "strategic resistance",  "Regional Power"),
            ("Israel",       "GPE", "State of Israel",                     "security primacy",      "Regional Power"),
            ("Ukraine",      "GPE", "Ukraine",                             "sovereign resilience",  "Conflict State"),
            ("North_Korea",  "GPE", "Democratic People's Republic of Korea","strategic deterrence", "Rogue State"),
            ("Belarus",      "GPE", "Republic of Belarus",                 "regime stability",      "Satellite State"),
            ("Saudi_Arabia", "GPE", "Kingdom of Saudi Arabia",             "oil supremacy",         "Regional Power"),
            ("Turkey",       "GPE", "Republic of Turkey",                  "strategic ambiguity",   "Regional Power"),
            ("Pakistan",     "GPE", "Islamic Republic of Pakistan",        "nuclear deterrence",    "Regional Power"),
            ("India",        "GPE", "Republic of India",                   "strategic autonomy",    "Emerging Power"),
            ("Germany",      "GPE", "Federal Republic of Germany",         "economic leadership",   "EU Anchor"),
            ("France",       "GPE", "French Republic",                     "independent deterrence","EU Anchor"),
            ("UK",           "GPE", "United Kingdom",                      "global influence",      "Post-Brexit Power"),
            ("Japan",        "GPE", "Japan",                               "technological prowess", "US Ally"),
            ("South_Korea",  "GPE", "Republic of Korea",                   "technological prowess", "US Ally"),
            ("Taiwan",       "GPE", "Republic of China / Taiwan",          "technological hub",     "Flashpoint"),
            ("Syria",        "GPE", "Syrian Arab Republic",                "fragile sovereignty",   "Conflict State"),
            ("Lebanon",      "GPE", "Lebanese Republic",                   "fractured state",       "Proxy Arena"),
            ("Yemen",        "GPE", "Republic of Yemen",                   "humanitarian crisis",   "Conflict State"),
            ("Iraq",         "GPE", "Republic of Iraq",                    "contested sovereignty",  "Proxy Arena"),
            ("Afghanistan",  "GPE", "Islamic Emirate of Afghanistan",      "regime consolidation",  "Failed State"),
            ("Libya",        "GPE", "State of Libya",                      "fragmented authority",  "Failed State"),
            ("Venezuela",    "GPE", "Bolivarian Republic of Venezuela",    "authoritarian resilience","Sanctioned State"),
            ("Cuba",         "GPE", "Republic of Cuba",                    "socialist resilience",  "Sanctioned State"),
            ("Myanmar",      "GPE", "Republic of the Union of Myanmar",    "military control",      "Junta State"),
            ("Ethiopia",     "GPE", "Federal Democratic Republic of Ethiopia","territorial integrity","Regional Power"),
            ("Sudan",        "GPE", "Republic of Sudan",                   "political fragmentation","Conflict State"),
            ("Brazil",       "GPE", "Federative Republic of Brazil",       "regional leadership",   "Emerging Power"),

            # ============================================================
            # GEOPOLITICS – International organisations (10)
            # ============================================================
            ("NATO",         "ORG", "North Atlantic Treaty Organization",  "collective defence",    "Military Alliance"),
            ("EU",           "ORG", "European Union",                      "multilateral order",    "Political Union"),
            ("UN",           "ORG", "United Nations",                      "global governance",     "Intergovernmental Body"),
            ("OPEC",         "ORG", "Organization of Petroleum Exporting Countries","supply control","Energy Cartel"),
            ("Hezbollah",    "ORG", "Lebanese militant/political group",   "armed resistance",      "Proxy Force"),
            ("Hamas",        "ORG", "Palestinian militant/political group","armed resistance",      "Proxy Force"),
            ("Wagner_Group", "ORG", "Russian private military company",    "deniable force",        "PMC"),
            ("ICC",          "ORG", "International Criminal Court",        "legal accountability",  "Judiciary Body"),
            ("SCO",          "ORG", "Shanghai Cooperation Organisation",   "counterbalance",        "Security Bloc"),
            ("IAEA",         "ORG", "International Atomic Energy Agency",  "nuclear oversight",     "UN Agency"),

            # ============================================================
            # GEOPOLITICS – Leaders / persons (12)
            # ============================================================
            ("Vladimir_Putin",       "PERSON", "President of Russia",             "power consolidation",  "President"),
            ("Xi_Jinping",           "PERSON", "General Secretary of CCP",        "regional dominance",   "General Secretary"),
            ("Kim_Jong_un",          "PERSON", "Supreme Leader of North Korea",   "strategic deterrence", "Supreme Leader"),
            ("Alexander_Lukashenko", "PERSON", "President of Belarus",            "regime survival",      "President"),
            ("Ali_Khamenei",         "PERSON", "Supreme Leader of Iran",          "theocratic authority", "Supreme Leader"),
            ("Benjamin_Netanyahu",   "PERSON", "Prime Minister of Israel",        "security primacy",     "Prime Minister"),
            ("Volodymyr_Zelensky",   "PERSON", "President of Ukraine",            "national survival",    "President"),
            ("Recep_Erdogan",        "PERSON", "President of Turkey",             "strategic pragmatism", "President"),
            ("Mohammed_bin_Salman",  "PERSON", "Crown Prince of Saudi Arabia",    "Vision 2030",          "Crown Prince"),
            ("Narendra_Modi",        "PERSON", "Prime Minister of India",         "strategic autonomy",   "Prime Minister"),
            ("Donald_Trump",         "PERSON", "US President (47th)",             "America First",        "President"),
            ("Hassan_Nasrallah",     "PERSON", "Former Secretary-General of Hezbollah","armed resistance","Militant Leader"),

            # ============================================================
            # GEOPOLITICS – Concepts / strategic assets (8)
            # ============================================================
            ("Strait_of_Hormuz",     "CONCEPT", "Strategic maritime chokepoint controlling ~20% global oil", "energy leverage",      "Chokepoint"),
            ("Nuclear_Deterrence",   "CONCEPT", "Mutual assured destruction doctrine",                       "existential threat",    "Doctrine"),
            ("Proxy_War",            "CONCEPT", "Conflict conducted through surrogate forces",               "deniable conflict",     "Strategy"),
            ("Economic_Sanctions",   "CONCEPT", "State-imposed economic restrictions",                       "coercive diplomacy",    "Policy Tool"),
            ("Disinformation",       "CONCEPT", "Deliberate spread of false information",                    "information warfare",   "Weapon"),
            ("Cybersecurity",        "CONCEPT", "Protection of digital infrastructure",                      "defensive resilience",  "Domain"),
            ("Nuclear_Program",      "CONCEPT", "State nuclear weapons or energy development",               "strategic deterrence",  "Asset"),
            ("Military_Alliance",    "CONCEPT", "Mutual defence treaty among states",                        "collective security",   "Framework"),

            # ============================================================
            # TECH / AI – Companies (22)
            # ============================================================
            ("OpenAI",          "ORG", "AI research lab behind GPT series",          "frontier AI development", "AI Lab"),
            ("Google",          "ORG", "Alphabet subsidiary, search and AI leader",  "information dominance",   "Tech Giant"),
            ("NVIDIA",          "ORG", "GPU and AI accelerator chipmaker",           "compute supremacy",       "Chip Maker"),
            ("TSMC",            "ORG", "Taiwan Semiconductor Manufacturing Company", "chip fabrication",        "Foundry"),
            ("Microsoft",       "ORG", "Cloud, software, and AI conglomerate",       "enterprise dominance",    "Tech Giant"),
            ("Meta",            "ORG", "Social media and open-source AI company",    "social influence",        "Tech Giant"),
            ("Apple",           "ORG", "Consumer electronics and services company",  "ecosystem lock-in",       "Tech Giant"),
            ("Amazon",          "ORG", "E-commerce and cloud computing giant",       "logistics dominance",     "Tech Giant"),
            ("AMD",             "ORG", "Advanced Micro Devices – CPU/GPU maker",     "competitive disruption",  "Chip Maker"),
            ("Intel",           "ORG", "Semiconductor and CPU manufacturer",         "legacy scale",            "Chip Maker"),
            ("Qualcomm",        "ORG", "Mobile chipset and 5G technology leader",    "mobile dominance",        "Chip Maker"),
            ("ByteDance",       "ORG", "Chinese tech giant behind TikTok/CapCut",   "data harvesting",         "Tech Giant"),
            ("Huawei",          "ORG", "Chinese telecoms and chip giant",            "state-backed scale",      "Tech Giant"),
            ("Samsung",         "ORG", "South Korean electronics and chip maker",    "vertical integration",    "Tech Giant"),
            ("DeepMind",        "ORG", "Google AI research lab",                     "scientific AI",           "AI Lab"),
            ("Anthropic",       "ORG", "Safety-focused AI research company",         "safe AI",                 "AI Lab"),
            ("xAI",             "ORG", "Elon Musk AI startup behind Grok",           "challenger disruption",   "AI Lab"),
            ("Mistral",         "ORG", "French open-source AI startup",              "European AI sovereignty", "AI Lab"),
            ("General_Catalyst","ORG", "Major Silicon Valley venture capital firm",  "capital allocation",      "VC Firm"),
            ("Sequoia_Capital", "ORG", "Premier Silicon Valley venture capital",     "ecosystem building",      "VC Firm"),
            ("SoftBank",        "ORG", "Japanese tech investment conglomerate",       "capital deployment",      "Investment Fund"),
            ("ASML",            "ORG", "Dutch semiconductor lithography monopoly",   "EUV monopoly",            "Chip Equipment"),

            # ============================================================
            # TECH / AI – Models / products (8)
            # ============================================================
            ("GPT4",            "CONCEPT", "OpenAI large language model series",        "frontier capability",   "AI Model"),
            ("Claude",          "CONCEPT", "Anthropic AI assistant model",              "constitutional AI",     "AI Model"),
            ("Gemini",          "CONCEPT", "Google multimodal AI model",                "multimodal fusion",     "AI Model"),
            ("LLaMA",           "CONCEPT", "Meta open-source LLM series",               "open-source AI",        "AI Model"),
            ("Grok",            "CONCEPT", "xAI large language model",                  "real-time grounding",   "AI Model"),
            ("Dreamina",        "CONCEPT", "ByteDance AI video generation model",       "generative media",      "AI Model"),
            ("Sora",            "CONCEPT", "OpenAI text-to-video generation model",     "generative media",      "AI Model"),
            ("Stable_Diffusion","CONCEPT", "Open-source image generation model",        "democratized generation","AI Model"),

            # ============================================================
            # TECH / AI – Infrastructure / concepts (18)
            # ============================================================
            ("Data_Center",       "CONCEPT", "Physical infrastructure for cloud and AI compute",  "compute backbone",     "Infrastructure"),
            ("Semiconductor",     "CONCEPT", "Silicon chip enabling all digital electronics",      "technological base",   "Strategic Asset"),
            ("Chip_Manufacturing","CONCEPT", "Fabrication of integrated circuits",                 "industrial bottleneck","Industry"),
            ("AI_Model",          "CONCEPT", "Trained neural network for inference tasks",         "intelligence automation","Technology"),
            ("Open_Source_AI",    "CONCEPT", "Publicly available AI model weights and code",       "democratization",      "Movement"),
            ("AI_Access",         "CONCEPT", "Availability of AI capabilities to end users",       "equitable empowerment","Outcome"),
            ("Job_Displacement",  "CONCEPT", "Automation-driven workforce disruption",             "economic disruption",  "Outcome"),
            ("AI_Regulation",     "CONCEPT", "Government policy and law governing AI",             "risk governance",      "Policy"),
            ("Tech_Innovation",   "CONCEPT", "Technological progress driving economic growth",      "creative destruction", "Driver"),
            ("Silicon_Valley",    "CONCEPT", "US technology industry hub in California",           "innovation ecosystem", "Ecosystem"),
            ("Venture_Capital",   "CONCEPT", "High-risk startup investment capital",               "growth acceleration",  "Finance"),
            ("5G_Network",        "CONCEPT", "Fifth-generation mobile telecommunications",        "connectivity leap",    "Infrastructure"),
            ("Quantum_Computing", "CONCEPT", "Post-classical computing paradigm",                 "cryptographic disruption","Emerging Tech"),
            ("Cybersecurity_Tech","CONCEPT", "Defensive and offensive digital security tools",    "digital resilience",   "Security Domain"),
            ("Cloud_Computing",   "CONCEPT", "On-demand internet-based computing services",       "utility compute",      "Infrastructure"),
            ("Energy",            "CONCEPT", "Power resources required by data centers and industry","resource dependency","Resource"),
            ("Export_Controls",   "CONCEPT", "Government restrictions on technology exports",     "strategic denial",     "Policy Tool"),
            ("AI_Startup",        "CONCEPT", "Early-stage company building AI products",          "disruptive innovation","Startup"),

            # ============================================================
            # ECONOMY – Concepts / institutions (28)
            # ============================================================
            ("Trade",              "CONCEPT", "Cross-border exchange of goods and services",        "economic interdependence","Activity"),
            ("Oil",                "CONCEPT", "Crude petroleum – primary global energy commodity",  "energy power",         "Commodity"),
            ("Natural_Gas",        "CONCEPT", "Fossil fuel energy commodity",                       "energy leverage",      "Commodity"),
            ("Supply_Chain",       "CONCEPT", "Network of production and logistics processes",      "operational continuity","System"),
            ("Inflation",          "CONCEPT", "Rise in general price level",                        "monetary erosion",     "Economic Force"),
            ("Interest_Rates",     "CONCEPT", "Central bank benchmark borrowing rates",             "monetary control",     "Policy Lever"),
            ("Markets",            "CONCEPT", "Financial and commodity trading markets",             "capital allocation",   "System"),
            ("Tariffs",            "CONCEPT", "Import/export duties imposed by governments",        "protectionism",        "Policy Tool"),
            ("Trade_War",          "CONCEPT", "Tit-for-tat tariff escalation between states",      "economic conflict",    "Conflict"),
            ("Dollar_Hegemony",    "CONCEPT", "US dollar as global reserve currency",               "monetary dominance",   "System"),
            ("De_Dollarization",   "CONCEPT", "Shift away from USD in global trade",               "monetary rebalancing",  "Trend"),
            ("Energy_Transition",  "CONCEPT", "Shift from fossil fuels to renewable energy",        "green transformation", "Trend"),
            ("Semiconductor_Trade","CONCEPT", "Global market for integrated circuits",              "strategic chokepoint", "Industry"),
            ("Tech_Tariff",        "CONCEPT", "Tariffs specifically targeting technology goods",    "economic weapon",      "Policy Tool"),
            ("WTO",                "ORG",     "World Trade Organization",                           "rules-based trade",    "Intergovernmental Body"),
            ("IMF",                "ORG",     "International Monetary Fund",                        "financial stability",  "Intergovernmental Body"),
            ("World_Bank",         "ORG",     "International development finance institution",     "development finance",  "Intergovernmental Body"),
            ("Federal_Reserve",    "ORG",     "US central bank",                                    "monetary authority",   "Central Bank"),
            ("ECB",                "ORG",     "European Central Bank",                              "eurozone monetary policy","Central Bank"),
            ("G7",                 "ORG",     "Group of 7 advanced economies",                      "Western coordination", "Forum"),
            ("G20",                "ORG",     "Group of 20 major economies",                        "global economic governance","Forum"),
            ("BRICS",              "ORG",     "Brazil-Russia-India-China-South Africa bloc",       "multipolar rebalancing","Bloc"),
            ("Tech_Stocks",        "CONCEPT", "Equity securities of technology companies",         "risk appetite",        "Asset Class"),
            ("Worker_Transition",  "CONCEPT", "Programs supporting workers displaced by automation","social stability",    "Policy"),
            ("Renewable_Energy",   "CONCEPT", "Solar, wind, and other clean energy sources",        "green power",         "Resource"),
            ("Carbon_Market",      "CONCEPT", "Emissions trading scheme",                           "climate finance",     "Market"),
            ("Crypto_Currency",    "CONCEPT", "Decentralised digital asset",                        "financial disruption", "Asset"),
            ("Debt_Crisis",        "CONCEPT", "Sovereign or corporate debt instability",            "systemic risk",       "Event"),

            # ============================================================
            # ECONOMY – Additional commodities / finance concepts (7)
            # ============================================================
            ("SWIFT",              "ORG",     "Society for Worldwide Interbank Financial Telecommunication","financial infrastructure","Payment Network"),
            ("Rare_Earth",         "CONCEPT", "Critical minerals for tech and defence manufacturing",    "resource leverage",    "Strategic Resource"),
            ("Lithium",            "CONCEPT", "Battery-grade mineral critical for EVs and storage",      "energy transition input","Critical Mineral"),
            ("Digital_Currency",   "CONCEPT", "Central bank digital currency (CBDC) initiatives",       "monetary sovereignty",  "Monetary Innovation"),
            ("Petrodollar",        "CONCEPT", "System of oil-for-dollar bilateral trade",                "energy-finance nexus",  "System"),
            ("LNG",                "CONCEPT", "Liquefied Natural Gas – exportable energy commodity",     "energy flexibility",    "Commodity"),
            ("Freight_Shipping",   "CONCEPT", "Global maritime cargo transportation",                   "trade logistics",       "Infrastructure"),

            # ============================================================
            # GEOPOLITICS – Additional nations & regions (14)
            # ============================================================
            ("Egypt",       "GPE", "Arab Republic of Egypt",                      "regional stability",    "Regional Power"),
            ("Jordan",      "GPE", "Hashemite Kingdom of Jordan",                 "buffer state",          "US Ally"),
            ("Qatar",       "GPE", "State of Qatar",                              "gas leverage",          "Gulf State"),
            ("UAE",         "GPE", "United Arab Emirates",                        "economic hub",          "Gulf State"),
            ("Morocco",     "GPE", "Kingdom of Morocco",                          "Atlantic gateway",      "Moderate State"),
            ("Mexico",      "GPE", "United Mexican States",                       "nearshoring hub",       "US Neighbour"),
            ("Indonesia",   "GPE", "Republic of Indonesia",                       "ASEAN leader",          "Emerging Power"),
            ("Vietnam",     "GPE", "Socialist Republic of Vietnam",               "manufacturing hub",     "ASEAN State"),
            ("Poland",      "GPE", "Republic of Poland",                          "NATO eastern flank",    "NATO Member"),
            ("Hungary",     "GPE", "Hungary",                                     "EU dissenter",          "NATO Member"),
            ("Finland",     "GPE", "Republic of Finland",                         "NATO newest member",    "NATO Member"),
            ("Australia",   "GPE", "Commonwealth of Australia",                   "AUKUS partner",         "US Ally"),
            ("Canada",      "GPE", "Canada",                                      "G7 member",             "US Ally"),
            ("Nigeria",     "GPE", "Federal Republic of Nigeria",                 "African leader",        "Regional Power"),

            # ============================================================
            # TECH / AI – Additional companies & concepts (8)
            # ============================================================
            ("Palantir",    "ORG", "Data analytics and government AI company",    "intelligence-grade AI", "AI Company"),
            ("SpaceX",      "ORG", "Elon Musk space and satellite company",       "space dominance",       "Aerospace"),
            ("Databricks",  "ORG", "Enterprise data and AI platform",             "data platform",         "AI Company"),
            ("Scale_AI",    "ORG", "AI training data and evaluation company",     "data annotation",       "AI Enabler"),
            ("CapCut",      "CONCEPT", "ByteDance AI-powered video editing app",  "consumer AI media",     "Application"),
            ("SMIC",        "ORG", "Semiconductor Manufacturing International Corporation","domestic fab", "Foundry"),
            ("Starlink",    "CONCEPT", "SpaceX low-earth orbit satellite internet","global connectivity",  "Infrastructure"),
            ("Edge_AI",     "CONCEPT", "AI inference on edge devices rather than cloud", "distributed compute","Technology"),

            # ============================================================
            # GEOPOLITICS – Referenced strategic locations (2)
            # ============================================================
            ("Suez_Canal",  "CONCEPT", "Egyptian maritime chokepoint linking Red Sea to Mediterranean", "logistics leverage", "Chokepoint"),
            ("TikTok",      "CONCEPT", "ByteDance short-video social media platform",  "data & influence",    "Social Platform"),
        ]
        # fmt: on

    # ------------------------------------------------------------------
    # Relationship data
    # ------------------------------------------------------------------

    def _build_relationships(
        self,
    ) -> List[Tuple[str, str, str, float, Optional[str], Optional[str]]]:
        """Return the master list of (source, target, rel_type, strength, virtue, role)."""
        # fmt: off
        return [
            # ============================================================
            # GEOPOLITICS – Rivalries & sanctions
            # ============================================================
            ("US",          "Iran",         "strategic_rival",    0.90, "coercive deterrence",   "Adversary"),
            ("US",          "Russia",       "strategic_rival",    0.90, "containment",            "Adversary"),
            ("US",          "China",        "strategic_competitor",0.85,"strategic competition",  "Competitor"),
            ("US",          "North_Korea",  "strategic_rival",    0.85, "nuclear containment",    "Adversary"),
            ("US",          "Iran",         "sanctions",          0.95, "economic coercion",      "Sanctioner"),
            ("US",          "Russia",       "sanctions",          0.90, "economic coercion",      "Sanctioner"),
            ("US",          "North_Korea",  "sanctions",          0.90, "economic coercion",      "Sanctioner"),
            ("US",          "Venezuela",    "sanctions",          0.85, "economic coercion",      "Sanctioner"),
            ("US",          "Cuba",         "sanctions",          0.80, "economic coercion",      "Sanctioner"),
            ("US",          "Myanmar",      "sanctions",          0.75, "human rights pressure",  "Sanctioner"),
            ("EU",          "Russia",       "sanctions",          0.90, "economic coercion",      "Sanctioner"),
            ("EU",          "Belarus",      "sanctions",          0.80, "democratic pressure",    "Sanctioner"),

            # ============================================================
            # GEOPOLITICS – Alliances & partnerships
            # ============================================================
            ("US",          "NATO",         "leads",              0.95, "alliance leadership",    "Hegemon"),
            ("US",          "Israel",       "strategic_partner",  0.95, "security guarantee",     "Patron"),
            ("US",          "Ukraine",      "military_support",   0.90, "proxy backing",          "Patron"),
            ("US",          "Japan",        "ally",               0.95, "mutual defence",         "Ally"),
            ("US",          "South_Korea",  "ally",               0.95, "mutual defence",         "Ally"),
            ("Russia",      "China",        "strategic_partner",  0.85, "multipolar alignment",   "Partner"),
            ("Russia",      "North_Korea",  "alliance",           0.85, "arms cooperation",       "Ally"),
            ("Russia",      "Belarus",      "controls",           0.90, "satellite relationship", "Patron"),
            ("Russia",      "Syria",        "military_support",   0.90, "regime protection",      "Patron"),
            ("Russia",      "Wagner_Group", "controls",           0.90, "deniable projection",    "Controller"),
            ("China",       "North_Korea",  "alliance",           0.80, "buffer state",           "Patron"),
            ("China",       "Pakistan",     "strategic_partner",  0.85, "CPEC investment",        "Partner"),
            ("China",       "SCO",          "leads",              0.85, "multilateral influence", "Leader"),
            ("NATO",        "Ukraine",      "supports",           0.85, "collective defence",     "Supporter"),
            ("Saudi_Arabia","OPEC",         "leads",              0.90, "price leadership",       "Leader"),
            ("Iran",        "SCO",          "member",             0.75, "multilateral hedging",   "Member"),
            ("Turkey",      "NATO",         "member",             0.75, "strategic ambiguity",    "Member"),
            ("India",       "SCO",          "member",             0.70, "strategic hedging",      "Member"),
            ("BRICS",       "De_Dollarization","promotes",        0.75, "monetary rebalancing",   "Driver"),

            # ============================================================
            # GEOPOLITICS – Military strikes & proxy conflicts
            # ============================================================
            ("Israel",      "Iran",         "military_strike",    0.90, "preventive action",      "Attacker"),
            ("Israel",      "Lebanon",      "military_strike",    0.85, "counter-Hezbollah",      "Attacker"),
            ("Israel",      "Hezbollah",    "military_strike",    0.90, "security operation",     "Attacker"),
            ("Israel",      "Hamas",        "military_strike",    0.90, "counter-terrorism",      "Attacker"),
            ("Israel",      "Syria",        "military_strike",    0.80, "strategic interdiction", "Attacker"),
            ("Russia",      "Ukraine",      "military_aggression",0.95, "expansionism",           "Aggressor"),
            ("US",          "Afghanistan",  "military_withdrawal",0.80, "strategic retrenchment", "Withdrawer"),
            ("Iran",        "Iraq",         "proxy_influence",    0.85, "regional hegemony",      "Influencer"),
            ("Iran",        "Yemen",        "proxy_support",      0.85, "regional hegemony",      "Patron"),
            ("Iran",        "Syria",        "proxy_support",      0.85, "regional hegemony",      "Patron"),

            # ============================================================
            # GEOPOLITICS – Iranian proxies & strategic assets
            # ============================================================
            ("Iran",        "Hezbollah",    "controls",           0.90, "proxy command",          "Controller"),
            ("Iran",        "Hamas",        "sponsors",           0.85, "proxy support",          "Sponsor"),
            ("Iran",        "Strait_of_Hormuz","controls",        0.90, "energy leverage",        "Controller"),
            ("Iran",        "Nuclear_Program","develops",         0.90, "deterrence build-up",    "Developer"),
            ("IAEA",        "Iran",         "inspects",           0.85, "nuclear oversight",      "Inspector"),
            ("IAEA",        "North_Korea",  "monitors",           0.75, "nuclear oversight",      "Monitor"),

            # ============================================================
            # GEOPOLITICS – Leadership
            # ============================================================
            ("Vladimir_Putin",       "Russia",   "leads",         0.95, "authoritarian control",  "Head of State"),
            ("Xi_Jinping",           "China",    "leads",         0.95, "party control",          "Head of State"),
            ("Kim_Jong_un",          "North_Korea","leads",       0.95, "totalitarian control",   "Supreme Leader"),
            ("Alexander_Lukashenko", "Belarus",  "leads",         0.90, "regime control",         "Head of State"),
            ("Ali_Khamenei",         "Iran",     "leads",         0.95, "theocratic control",     "Supreme Leader"),
            ("Benjamin_Netanyahu",   "Israel",   "leads",         0.90, "political control",      "Prime Minister"),
            ("Volodymyr_Zelensky",   "Ukraine",  "leads",         0.90, "wartime leadership",     "Head of State"),
            ("Recep_Erdogan",        "Turkey",   "leads",         0.90, "presidential control",   "Head of State"),
            ("Mohammed_bin_Salman",  "Saudi_Arabia","leads",      0.90, "Vision 2030 agenda",     "Crown Prince"),
            ("Narendra_Modi",        "India",    "leads",         0.90, "development agenda",     "Prime Minister"),
            ("Donald_Trump",         "US",       "leads",         0.90, "America First",          "President"),
            ("Hassan_Nasrallah",     "Hezbollah","led",           0.85, "armed resistance",       "Former Leader"),

            # ============================================================
            # GEOPOLITICS – Nuclear
            # ============================================================
            ("North_Korea",  "Nuclear_Deterrence","uses",         0.90, "regime survival",        "Nuclear Power"),
            ("Russia",       "Nuclear_Deterrence","uses",         0.95, "strategic deterrence",   "Nuclear Power"),
            ("US",           "Nuclear_Deterrence","uses",         0.95, "extended deterrence",    "Nuclear Power"),
            ("Iran",         "Nuclear_Deterrence","pursues",      0.85, "deterrence aspiration",  "Near-Nuclear"),
            ("Pakistan",     "Nuclear_Deterrence","uses",         0.85, "existential deterrence", "Nuclear Power"),
            ("India",        "Nuclear_Deterrence","uses",         0.85, "strategic deterrence",   "Nuclear Power"),

            # ============================================================
            # TECH / AI – Development & ownership
            # ============================================================
            ("OpenAI",      "GPT4",         "develops",           0.95, "frontier development",   "Developer"),
            ("OpenAI",      "Sora",         "develops",           0.90, "generative media",       "Developer"),
            ("Anthropic",   "Claude",       "develops",           0.95, "safety development",     "Developer"),
            ("Google",      "Gemini",       "develops",           0.95, "multimodal development", "Developer"),
            ("Google",      "DeepMind",     "owns",               0.95, "AI investment",          "Parent"),
            ("Meta",        "LLaMA",        "develops",           0.90, "open-source release",    "Developer"),
            ("xAI",         "Grok",         "develops",           0.90, "real-time AI",           "Developer"),
            ("ByteDance",   "Dreamina",     "develops",           0.90, "generative video AI",    "Developer"),
            ("Microsoft",   "OpenAI",       "invests",            0.90, "strategic investment",   "Investor"),
            ("SoftBank",    "OpenAI",       "invests",            0.85, "capital deployment",     "Investor"),
            ("General_Catalyst","AI_Startup","funds",             0.85, "growth acceleration",    "VC"),
            ("Sequoia_Capital","AI_Startup","funds",              0.85, "growth acceleration",    "VC"),

            # ============================================================
            # TECH / AI – Compute infrastructure
            # ============================================================
            ("NVIDIA",      "Data_Center",  "supplies_gpu",       0.95, "compute monopoly",       "Supplier"),
            ("TSMC",        "Semiconductor","manufactures",       0.95, "fabrication monopoly",   "Manufacturer"),
            ("ASML",        "TSMC",         "supplies_euv",       0.95, "EUV monopoly",           "Supplier"),
            ("ASML",        "Semiconductor","enables",            0.95, "EUV lithography",        "Enabler"),
            ("Intel",       "Semiconductor","manufactures",       0.85, "legacy fabrication",     "Manufacturer"),
            ("Samsung",     "Semiconductor","manufactures",       0.90, "advanced nodes",         "Manufacturer"),
            ("NVIDIA",      "AI_Model",     "accelerates",        0.95, "GPU compute",            "Enabler"),
            ("Data_Center", "Energy",       "consumes",           0.90, "power demand",           "Consumer"),
            ("Data_Center", "Cloud_Computing","enables",          0.90, "infrastructure basis",   "Enabler"),
            ("Cloud_Computing","AI_Model",  "hosts",              0.90, "deployment platform",    "Platform"),
            ("5G_Network",  "Data_Center",  "connects",           0.80, "edge connectivity",      "Connector"),

            # ============================================================
            # TECH / AI – AI models & capabilities
            # ============================================================
            ("AI_Model",    "Job_Displacement","causes",          0.85, "automation wave",        "Cause"),
            ("AI_Model",    "AI_Regulation","triggers",           0.80, "regulatory response",    "Cause"),
            ("AI_Model",    "Tech_Innovation","drives",           0.85, "capability frontier",    "Driver"),
            ("Open_Source_AI","AI_Access",  "democratizes",       0.80, "open distribution",      "Enabler"),
            ("Open_Source_AI","AI_Startup", "enables",            0.80, "startup foundation",     "Enabler"),
            ("AI_Startup",  "Venture_Capital","raises_funding_from",0.85,"capital formation",     "Recipient"),
            ("AI_Startup",  "Tech_Innovation","drives",           0.80, "disruptive creation",    "Driver"),
            ("GPT4",        "Job_Displacement","contributes_to",  0.80, "knowledge worker impact","Contributor"),
            ("LLaMA",       "Open_Source_AI","exemplifies",       0.85, "open weights",           "Example"),
            ("Dreamina",    "AI_Access",    "expands",            0.75, "consumer AI video",      "Expander"),

            # ============================================================
            # TECH / AI – Geopolitical tech competition
            # ============================================================
            ("US",          "Export_Controls","implements",       0.90, "strategic denial",       "Regulator"),
            ("US",          "TSMC",         "partners",           0.85, "reshoring strategy",     "Partner"),
            ("US",          "NVIDIA",       "restricts_exports",  0.85, "chip export controls",   "Regulator"),
            ("China",       "TSMC",         "competes_with",      0.80, "semiconductor catch-up", "Competitor"),
            ("China",       "Huawei",       "supports",           0.90, "national champion",      "Patron"),
            ("China",       "SMIC",         "supports",           0.85, "domestic fab",           "Patron"),
            ("Huawei",      "5G_Network",   "builds",             0.85, "infrastructure control", "Builder"),
            ("Huawei",      "Semiconductor","develops",           0.80, "vertical integration",   "Developer"),
            ("Export_Controls","TSMC",      "affects",            0.85, "supply chain impact",    "Regulator"),
            ("Export_Controls","NVIDIA",    "affects",            0.85, "chip supply impact",     "Regulator"),
            ("Export_Controls","Huawei",    "restricts",          0.90, "technology denial",      "Restrictor"),
            ("Taiwan",      "TSMC",         "hosts",              0.95, "strategic asset",        "Host"),
            ("China",       "Taiwan",       "claims_sovereignty", 0.95, "territorial claim",      "Claimant"),

            # ============================================================
            # ECONOMY – Trade & tariffs
            # ============================================================
            ("WTO",         "Trade",        "regulates",          0.90, "rules-based order",      "Regulator"),
            ("WTO",         "Tariffs",      "adjudicates",        0.85, "dispute resolution",     "Adjudicator"),
            ("US",          "Trade_War",    "initiates",          0.85, "protectionist policy",   "Initiator"),
            ("China",       "Trade_War",    "retaliates",         0.85, "reciprocal response",    "Retaliator"),
            ("Tariffs",     "Supply_Chain", "disrupts",           0.85, "cost increase",          "Disruptor"),
            ("Tariffs",     "Inflation",    "causes",             0.80, "price level impact",     "Cause"),
            ("Trade_War",   "Supply_Chain", "disrupts",           0.85, "logistics disruption",   "Disruptor"),
            ("Trade_War",   "Markets",      "volatilises",        0.80, "uncertainty premium",    "Volatiliser"),
            ("Tech_Tariff", "Semiconductor_Trade","restricts",    0.85, "strategic restriction",  "Restrictor"),
            ("US",          "Tech_Tariff",  "imposes",            0.85, "economic weapon",        "Imposer"),
            ("China",       "Semiconductor_Trade","dominates",    0.80, "supply chain control",   "Dominator"),

            # ============================================================
            # ECONOMY – Energy & oil
            # ============================================================
            ("Oil",         "Strait_of_Hormuz","flows_through",   0.90, "chokepoint dependency",  "Commodity"),
            ("Natural_Gas", "Trade",        "drives",             0.85, "energy trade",           "Driver"),
            ("OPEC",        "Oil",          "controls_supply",    0.90, "price control",          "Controller"),
            ("Saudi_Arabia","Oil",          "exports",            0.90, "petro-power",            "Exporter"),
            ("Russia",      "Natural_Gas",  "exports",            0.90, "energy leverage",        "Exporter"),
            ("Iran",        "Oil",          "exports",            0.80, "sanctioned exports",     "Exporter"),
            ("Energy_Transition","Oil",     "threatens",          0.75, "demand reduction",       "Disruptor"),
            ("Renewable_Energy","Energy_Transition","enables",    0.85, "clean energy supply",    "Enabler"),
            ("Data_Center", "Renewable_Energy","demands",         0.75, "green compute",          "Demander"),
            ("Energy",      "Inflation",    "drives",             0.80, "cost push inflation",    "Driver"),
            ("Energy",      "Supply_Chain", "underpins",          0.85, "operational backbone",   "Underpinner"),

            # ============================================================
            # ECONOMY – Finance & monetary
            # ============================================================
            ("Federal_Reserve","Interest_Rates","controls",      0.95, "monetary authority",      "Controller"),
            ("ECB",          "Interest_Rates","controls",        0.90, "eurozone policy",         "Controller"),
            ("Interest_Rates","Markets",     "influences",        0.90, "capital cost signal",    "Influencer"),
            ("Interest_Rates","Tech_Stocks", "influences",        0.85, "valuation impact",       "Influencer"),
            ("Inflation",    "Interest_Rates","drives",           0.85, "policy response",        "Driver"),
            ("Debt_Crisis",  "Markets",      "destabilises",      0.85, "systemic contagion",     "Destabiliser"),
            ("Dollar_Hegemony","Trade",      "dominates",         0.90, "invoicing currency",     "Dominator"),
            ("De_Dollarization","Dollar_Hegemony","challenges",   0.75, "currency rebalancing",   "Challenger"),
            ("IMF",          "Debt_Crisis",  "manages",           0.85, "lender of last resort",  "Manager"),
            ("World_Bank",   "Renewable_Energy","finances",       0.80, "development finance",    "Financier"),
            ("G7",           "Russia",       "sanctions",         0.85, "Western coordination",   "Sanctioner"),
            ("G7",           "Trade",        "coordinates",       0.80, "economic governance",    "Coordinator"),
            ("G20",          "Trade",        "governs",           0.80, "global coordination",    "Coordinator"),
            ("BRICS",        "Dollar_Hegemony","challenges",      0.75, "multipolar finance",     "Challenger"),

            # ============================================================
            # ECONOMY – Supply chain & tech industry
            # ============================================================
            ("Silicon_Valley","Tech_Innovation","hub_of",         0.90, "innovation nucleus",     "Hub"),
            ("Silicon_Valley","Venture_Capital","attracts",       0.85, "capital concentration",  "Hub"),
            ("Supply_Chain", "Semiconductor", "depends_on",       0.90, "critical input",         "Dependent"),
            ("Supply_Chain", "Trade",        "enables",           0.85, "logistics basis",        "Enabler"),
            ("Semiconductor_Trade","Supply_Chain","shapes",       0.85, "bottleneck control",     "Shaper"),
            ("Carbon_Market","Energy_Transition","finances",      0.80, "climate mechanism",      "Financer"),
            ("Job_Displacement","Worker_Transition","necessitates",0.85,"retraining need",        "Cause"),
            ("Venture_Capital","Tech_Stocks","affects",           0.80, "portfolio valuation",    "Influencer"),
            ("Crypto_Currency","Dollar_Hegemony","challenges",    0.70, "decentralised finance",  "Challenger"),
            ("AI_Model",     "Markets",      "influences",        0.75, "algorithmic trading",    "Influencer"),

            # ============================================================
            # CROSS-DOMAIN – Geopolitics ↔ Tech
            # ============================================================
            ("US",          "AI_Regulation","implements",         0.85, "national security AI",   "Regulator"),
            ("China",       "AI_Regulation","implements",         0.85, "state-directed AI",      "Regulator"),
            ("EU",          "AI_Regulation","implements",         0.90, "risk-based regulation",  "Regulator"),
            ("US",          "Cybersecurity_Tech","invests",       0.85, "national defence",       "Investor"),
            ("Russia",      "Cybersecurity","uses",               0.85, "offensive cyber",        "Actor"),
            ("China",       "Cybersecurity","uses",               0.85, "state surveillance",     "Actor"),
            ("North_Korea", "Cybersecurity","uses",               0.80, "revenue generation",     "Actor"),
            ("US",          "Quantum_Computing","invests",        0.80, "strategic edge",         "Investor"),
            ("China",       "Quantum_Computing","invests",        0.80, "strategic edge",         "Investor"),
            ("Pakistan",    "US",           "mediates",           0.75, "diplomatic bridge",      "Mediator"),
            ("Pakistan",    "Iran",         "mediates",           0.70, "regional diplomacy",     "Mediator"),

            # ============================================================
            # CROSS-DOMAIN – Tech ↔ Economy
            # ============================================================
            ("AI_Startup",  "Venture_Capital","depends_on",       0.85, "funding dependency",     "Dependent"),
            ("Tech_Innovation","Markets",    "drives",             0.85, "valuation driver",       "Driver"),
            ("Semiconductor","Supply_Chain", "is_critical_to",    0.90, "chokepoint",             "Critical Input"),
            ("Data_Center", "Carbon_Market","participates_in",    0.75, "ESG compliance",         "Participant"),
            ("Crypto_Currency","Markets",   "is_traded_in",       0.75, "speculative asset",      "Asset"),
            ("AI_Model",     "Tech_Stocks", "lifts",              0.80, "AI premium",             "Driver"),

            # ============================================================
            # GEOPOLITICS – Additional bilateral & regional (30)
            # ============================================================
            ("Qatar",       "Hamas",        "sponsors",           0.80, "political patronage",    "Sponsor"),
            ("Qatar",       "Natural_Gas",  "exports",            0.90, "LNG leverage",           "Exporter"),
            ("UAE",         "Israel",       "normalises",         0.80, "Abraham Accords",        "Partner"),
            ("Saudi_Arabia","Israel",       "normalises",         0.70, "strategic alignment",    "Partner"),
            ("Egypt",       "Hamas",        "mediates",           0.75, "border control",         "Mediator"),
            ("Jordan",      "Israel",       "ally",               0.75, "peace treaty",           "Treaty Partner"),
            ("Turkey",      "Russia",       "economic_partner",   0.75, "TurkStream gas",         "Partner"),
            ("Turkey",      "Ukraine",      "arms_supplier",      0.80, "Bayraktar drones",       "Supplier"),
            ("Turkey",      "NATO",         "leverage",           0.75, "strategic bottleneck",   "Gatekeeper"),
            ("India",       "Russia",       "oil_buyer",          0.80, "discounted crude",       "Buyer"),
            ("India",       "US",           "partner",            0.80, "Quad alignment",         "Partner"),
            ("India",       "China",        "strategic_rival",    0.85, "border tension",         "Adversary"),
            ("Australia",   "China",        "trade_partner",      0.75, "commodity exports",      "Trade Partner"),
            ("Australia",   "US",           "ally",               0.90, "AUKUS pact",             "Ally"),
            ("South_Korea", "North_Korea",  "strategic_rival",    0.90, "divided peninsula",      "Adversary"),
            ("Japan",       "China",        "strategic_rival",    0.80, "territorial dispute",    "Adversary"),
            ("Vietnam",     "China",        "strategic_rival",    0.75, "South China Sea",        "Adversary"),
            ("Poland",      "Russia",       "strategic_rival",    0.90, "NATO frontline",         "Adversary"),
            ("Poland",      "Ukraine",      "supports",           0.90, "solidarity",             "Supporter"),
            ("Hungary",     "Russia",       "partner",            0.75, "EU dissenter",           "Partner"),
            ("Finland",     "NATO",         "member",             0.90, "Nordic security",        "Member"),
            ("Mexico",      "US",           "trade_partner",      0.85, "USMCA",                  "Trade Partner"),
            ("Indonesia",   "China",        "trade_partner",      0.80, "investment ties",        "Trade Partner"),
            ("Nigeria",     "Oil",          "exports",            0.85, "petro-state",            "Exporter"),
            ("Brazil",      "BRICS",        "member",             0.80, "emerging market",        "Member"),
            ("Brazil",      "Trade",        "promotes",           0.75, "commodity exporter",     "Promoter"),
            ("Canada",      "US",           "ally",               0.90, "NORAD",                  "Ally"),
            ("Canada",      "G7",           "member",             0.85, "Western alignment",      "Member"),
            ("Morocco",     "EU",           "partner",            0.75, "energy corridor",        "Partner"),
            ("Egypt",       "Suez_Canal",   "controls",           0.90, "strategic waterway",     "Controller"),

            # ============================================================
            # GEOPOLITICS – Additional strategic concepts (10)
            # ============================================================
            ("Proxy_War",   "Iran",         "characterises",      0.85, "Iranian strategy",       "Actor"),
            ("Proxy_War",   "Russia",       "characterises",      0.85, "Russian strategy",       "Actor"),
            ("Disinformation","Russia",     "originates_from",    0.85, "info warfare",           "Source"),
            ("Disinformation","China",      "originates_from",    0.80, "influence operations",   "Source"),
            ("Military_Alliance","US",      "anchors",            0.95, "alliance leadership",    "Anchor"),
            ("Military_Alliance","NATO",    "institutionalises",  0.95, "collective structure",   "Institution"),
            ("Economic_Sanctions","US",     "leads",              0.90, "financial enforcement",  "Leader"),
            ("Economic_Sanctions","EU",     "implements",         0.85, "Brussels mechanism",     "Implementer"),
            ("Nuclear_Program","Iran",      "pursues",            0.90, "deterrence bid",         "Pursuer"),
            ("Nuclear_Program","North_Korea","owns",              0.90, "regime guarantee",       "Owner"),

            # ============================================================
            # TECH / AI – Additional model / company relationships (25)
            # ============================================================
            ("Mistral",     "Open_Source_AI","exemplifies",       0.85, "European open weights",  "Example"),
            ("Stable_Diffusion","Open_Source_AI","exemplifies",   0.85, "image generation open",  "Example"),
            ("Palantir",    "AI_Model",     "deploys",            0.85, "government AI",          "Deployer"),
            ("Palantir",    "US",           "contracts",          0.85, "defence contracts",      "Contractor"),
            ("SpaceX",      "Starlink",     "operates",           0.90, "satellite internet",     "Operator"),
            ("Starlink",    "Ukraine",      "supports",           0.90, "battlefield connectivity","Enabler"),
            ("Databricks",  "AI_Model",     "trains",             0.85, "MLOps platform",         "Trainer"),
            ("Scale_AI",    "AI_Model",     "trains",             0.85, "data annotation",        "Enabler"),
            ("CapCut",      "Dreamina",     "integrates",         0.85, "app integration",        "Host"),
            ("CapCut",      "Job_Displacement","impacts",         0.75, "creator economy",        "Influencer"),
            ("ByteDance",   "TikTok",       "owns",               0.95, "social platform",        "Owner"),
            ("SMIC",        "China",        "serves",             0.90, "domestic champion",      "National Champion"),
            ("AMD",         "NVIDIA",       "competes_with",      0.85, "GPU market rivalry",     "Competitor"),
            ("AMD",         "Data_Center",  "supplies",           0.85, "GPU supply",             "Supplier"),
            ("Intel",       "AI_Model",     "accelerates",        0.75, "Gaudi accelerators",     "Supplier"),
            ("Qualcomm",    "Edge_AI",      "enables",            0.85, "on-device inference",    "Enabler"),
            ("Apple",       "Edge_AI",      "leads",              0.85, "Neural Engine",          "Leader"),
            ("Amazon",      "Cloud_Computing","leads",            0.90, "AWS leadership",         "Leader"),
            ("Microsoft",   "Cloud_Computing","leads",            0.90, "Azure leadership",       "Leader"),
            ("Google",      "Cloud_Computing","leads",            0.85, "GCP platform",           "Leader"),
            ("xAI",         "Venture_Capital","raises_funding_from",0.85,"Series B round",        "Recipient"),
            ("Anthropic",   "Venture_Capital","raises_funding_from",0.85,"safety AI funding",     "Recipient"),
            ("Mistral",     "Venture_Capital","raises_funding_from",0.80,"European AI fund",      "Recipient"),
            ("OpenAI",      "AI_Regulation","triggers",           0.85, "regulatory catalyst",    "Catalyst"),
            ("AI_Startup",  "AI_Model",     "builds",             0.85, "core product",           "Builder"),

            # ============================================================
            # ECONOMY – Additional trade & resource (30)
            # ============================================================
            ("Strait_of_Hormuz","Trade",    "enables",            0.90, "maritime trade",         "Enabler"),
            ("LNG",         "Trade",        "drives",             0.85, "energy trade",           "Commodity"),
            ("LNG",         "Qatar",        "exported_by",        0.90, "Qatari leverage",        "Origin"),
            ("LNG",         "US",           "exported_by",        0.85, "energy security",        "Origin"),
            ("Rare_Earth",  "China",        "dominated_by",       0.90, "supply monopoly",        "Dominator"),
            ("Rare_Earth",  "Semiconductor","critical_for",       0.90, "manufacturing input",    "Input"),
            ("Rare_Earth",  "Supply_Chain", "disrupts_if_restricted",0.85,"geopolitical weapon",  "Risk"),
            ("Lithium",     "Renewable_Energy","critical_for",    0.90, "battery storage",        "Input"),
            ("Lithium",     "Energy_Transition","enables",        0.85, "EV battery basis",       "Enabler"),
            ("Freight_Shipping","Trade",    "enables",            0.90, "maritime logistics",     "Enabler"),
            ("Freight_Shipping","Supply_Chain","component_of",    0.85, "logistics system",       "Component"),
            ("Petrodollar", "Dollar_Hegemony","reinforces",       0.85, "oil-dollar nexus",       "Reinforcer"),
            ("Petrodollar", "Saudi_Arabia", "anchored_by",        0.85, "bilateral deal",         "Anchor"),
            ("SWIFT",       "Trade",        "facilitates",        0.90, "payment settlement",     "Facilitator"),
            ("SWIFT",       "Russia",       "excludes",           0.90, "sanctions tool",         "Excluder"),
            ("SWIFT",       "Dollar_Hegemony","reinforces",       0.85, "USD clearing",           "Reinforcer"),
            ("Digital_Currency","Dollar_Hegemony","challenges",   0.75, "CBDC competition",       "Challenger"),
            ("Digital_Currency","China",    "developed_by",       0.85, "digital yuan",           "Developer"),
            ("De_Dollarization","BRICS",    "promoted_by",        0.80, "multipolar finance",     "Promoter"),
            ("Trade_War",   "Tariffs",      "manifests_as",       0.85, "policy instrument",      "Manifestation"),
            ("Trade_War",   "Tech_Tariff",  "includes",           0.80, "sector-specific",        "Component"),
            ("G20",         "Debt_Crisis",  "coordinates_response",0.80,"systemic response",      "Coordinator"),
            ("IMF",         "Trade",        "monitors",           0.80, "financial oversight",    "Monitor"),
            ("Debt_Crisis", "Supply_Chain", "disrupts",           0.80, "credit tightening",      "Disruptor"),
            ("Carbon_Market","EU",          "governed_by",        0.85, "EU ETS",                 "Governor"),
            ("Renewable_Energy","Supply_Chain","reshapes",        0.80, "green transition",       "Reshaper"),
            ("Energy_Transition","Supply_Chain","reshapes",       0.80, "decarbonisation",        "Reshaper"),
            ("Worker_Transition","AI_Regulation","informs",       0.75, "policy linkage",         "Informer"),
            ("Inflation",   "Trade",        "affects",            0.80, "import/export cost",     "Disruptor"),
            ("Interest_Rates","Debt_Crisis","triggers",           0.80, "debt service cost",      "Trigger"),

            # ============================================================
            # CROSS-DOMAIN – Additional (15)
            # ============================================================
            ("Export_Controls","Rare_Earth","complements",        0.80, "supply denial",          "Complement"),
            ("Export_Controls","China",     "targets",            0.85, "tech decoupling",        "Target"),
            ("Huawei",      "Export_Controls","subject_to",       0.90, "US restrictions",        "Subject"),
            ("Taiwan",      "Semiconductor_Trade","dominates",    0.90, "TSMC share",             "Dominator"),
            ("Taiwan",      "US",           "partnered_with",     0.85, "CHIPS Act",              "Partner"),
            ("Starlink",    "Cybersecurity_Tech","enhances",      0.80, "resilient comms",        "Enhancer"),
            ("AI_Regulation","Export_Controls","complements",     0.80, "governance linkage",     "Complement"),
            ("Palantir",    "Cybersecurity_Tech","provides",      0.85, "defence intelligence",   "Provider"),
            ("SpaceX",      "US",           "supports",           0.85, "national capability",    "Supporter"),
            ("BRICS",       "SWIFT",        "seeks_alternative_to",0.75,"payment independence",   "Challenger"),
            ("Digital_Currency","Trade",    "may_transform",      0.75, "settlement future",      "Transformer"),
            ("Quantum_Computing","Cybersecurity","threatens",     0.80, "encryption break",       "Threat"),
            ("Quantum_Computing","Cybersecurity_Tech","threatens",0.80, "post-quantum need",      "Threat"),
            ("Edge_AI",     "AI_Access",    "expands",            0.80, "offline inference",      "Expander"),
            ("Edge_AI",     "Job_Displacement","contributes_to",  0.75, "automation at edge",     "Contributor"),

            # ============================================================
            # GEOPOLITICS – Additional nation relationships (20)
            # ============================================================
            ("Suez_Canal",  "Trade",        "enables",            0.90, "global maritime route",  "Enabler"),
            ("Egypt",       "EU",           "partner",            0.75, "Mediterranean partnership","Partner"),
            ("UAE",         "US",           "ally",               0.85, "Gulf security",          "Ally"),
            ("UAE",         "China",        "economic_partner",   0.80, "Belt and Road",          "Partner"),
            ("Qatar",       "US",           "ally",               0.80, "Al-Udeid base",          "Host"),
            ("Nigeria",     "OPEC",         "member",             0.85, "oil production",         "Member"),
            ("Indonesia",   "US",           "partner",            0.75, "Indo-Pacific strategy",  "Partner"),
            ("Vietnam",     "US",           "partner",            0.80, "supply chain shift",     "Partner"),
            ("Mexico",      "Trade",        "benefits_from",      0.80, "nearshoring trend",      "Beneficiary"),
            ("Canada",      "Trade",        "promotes",           0.80, "G7 trade policy",        "Promoter"),
            ("Australia",   "India",        "partner",            0.80, "Quad member",            "Partner"),
            ("Finland",     "Russia",       "strategic_rival",    0.90, "border tension",         "Adversary"),
            ("Poland",      "NATO",         "member",             0.90, "eastern anchor",         "Member"),
            ("Hungary",     "EU",           "member",             0.75, "Orbán dissent",          "Member"),
            ("Morocco",     "Renewable_Energy","invests",         0.80, "green energy transition","Investor"),
            ("Jordan",      "US",           "ally",               0.80, "security partner",       "Ally"),
            ("TikTok",      "US",           "scrutinised_by",     0.85, "national security",      "Subject"),
            ("TikTok",      "AI_Regulation","subject_to",         0.80, "platform regulation",    "Subject"),
            ("ByteDance",   "China",        "headquartered_in",   0.90, "state nexus",            "National"),
            ("Palantir",    "NATO",         "supports",           0.80, "defence AI",             "Supporter"),
        ]
        # fmt: on

    # ------------------------------------------------------------------
    # Seeding methods
    # ------------------------------------------------------------------

    def seed_entities(self) -> Tuple[int, List[str]]:
        """Insert all entities using idempotent MERGE.

        Returns:
            (count_created, list_of_entity_names)
        """
        if not self._available or not self._conn:
            logger.warning("KuzuDB not available; skipping entity seeding")
            return 0, []

        entities = self._build_entities()
        count = 0
        names: List[str] = []

        for name, etype, desc, virtue, role in entities:
            names.append(name)
            try:
                n = _esc(name)
                d = _esc(desc) if desc else ""
                v = f"'{_esc(virtue)}'" if virtue else "null"
                r = f"'{_esc(role)}'"   if role   else "null"

                query = (
                    f"MERGE (e:Entity {{name: '{n}'}}) "
                    f"ON CREATE SET "
                    f"  e.type = '{etype}', "
                    f"  e.description = '{d}', "
                    f"  e.virtue = {v}, "
                    f"  e.role = {r} "
                    f"RETURN e.name"
                )
                result = self._conn.execute(query)
                if result.has_next():
                    count += 1
                    logger.debug("Entity seeded: %s", name)
            except Exception as exc:
                logger.debug("Entity seed skipped (duplicate?): %s – %s", name, exc)

        self.entities_created = count
        logger.info("Seeded %d entities", count)
        return count, names

    def seed_relationships(self, entity_names: List[str]) -> int:  # noqa: ARG002
        """Insert all relationships using idempotent MERGE.

        Args:
            entity_names: Accepted for API compatibility with callers that
                pass the list returned by :meth:`seed_entities`.  Not used
                internally because relationships reference entity names
                directly from :meth:`_build_relationships`.

        Returns:
            Count of relationships created.
        """
        if not self._available or not self._conn:
            logger.warning("KuzuDB not available; skipping relationship seeding")
            return 0

        relationships = self._build_relationships()
        count = 0

        for source, target, rel_type, strength, virtue, role in relationships:
            try:
                s = _esc(source)
                t = _esc(target)
                rt = _esc(rel_type)
                v = f"'{_esc(virtue)}'" if virtue else "null"
                r = f"'{_esc(role)}'"   if role   else "null"

                query = (
                    f"MATCH (src:Entity {{name: '{s}'}}), "
                    f"(tgt:Entity {{name: '{t}'}}) "
                    f"MERGE (src)-[rel:RELATED {{relation_type: '{rt}'}}]->(tgt) "
                    f"ON CREATE SET "
                    f"  rel.strength = {strength}, "
                    f"  rel.virtue = {v}, "
                    f"  rel.role = {r} "
                    f"RETURN rel.relation_type"
                )
                result = self._conn.execute(query)
                if result.has_next():
                    count += 1
                    logger.debug(
                        "Relationship seeded: %s --%s--> %s (%.2f)",
                        source, rel_type, target, strength,
                    )
            except Exception as exc:
                logger.debug(
                    "Relationship seed skipped (duplicate?): %s --%s--> %s – %s",
                    source, rel_type, target, exc,
                )

        self.relationships_created = count
        logger.info("Seeded %d relationships", count)
        return count

    def seed_ontology(self) -> Tuple[int, int]:
        """Run the full seeding pipeline.

        Returns:
            (entities_created, relationships_created)
        """
        if not self._available:
            logger.error("KuzuDB not available – cannot seed")
            return 0, 0

        logger.info("Starting comprehensive ontology seeding…")
        self._ensure_schema()

        ent_count, entity_names = self.seed_entities()
        rel_count = self.seed_relationships(entity_names)

        logger.info(
            "✅ Ontology seeding complete: %d entities + %d relationships",
            ent_count,
            rel_count,
        )
        return ent_count, rel_count


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point when run as a module."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    )

    _ensure_backend_importable()

    seeder = SeedOntologySeeder(db_path="./data/kuzu_db")
    if not seeder._available:
        logger.error("KuzuDB connection failed – cannot proceed")
        sys.exit(1)

    ent_count, rel_count = seeder.seed_ontology()

    print()
    print("=" * 70)
    print("🎯 SEED ONTOLOGY COMPLETE")
    print("=" * 70)
    print(f"📊 Inserted {ent_count} nodes")
    print(f"🔗 Inserted {rel_count} relationships")
    print(f"⏰ Timestamp: {datetime.now().isoformat()}")
    print("=" * 70)


if __name__ == "__main__":
    main()