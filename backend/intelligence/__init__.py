"""
EL'druin Intelligence Platform – Bayesian Bridge (Logic Auditor)
================================================================

Lightweight Bayesian probability tracking system that mathematically
quantifies every logical inference in the knowledge graph.

Modules:
    models                 – Pydantic data-structures (ReasoningPath, ProbabilityTree)
    logic_auditor          – ReasoningPathRecorder: records the full inference chain
    probability_tree       – ProbabilityTreeBuilder: generates alternative interpretations
    sacred_sword_analyzer  – SacredSwordAnalyzer: 4-step ontological reasoning engine
    deduction_engine       – DeductionEngine: 推演灵魂 – forces LLM to deduce from paths
    grounded_analyzer      – OntologyGroundedAnalyzer: combines KuzuDB + DeductionEngine
"""
