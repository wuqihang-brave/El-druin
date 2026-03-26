async def perform_deduction(news_content: str, kuzu_conn: Any) -> Dict[str, Any]:
    """Full Graph-Grounded Deduction pipeline with fallback and confidence boost."""
    _ensure_backend_on_path()

    # Step 1 – Extract entities
    entities = await extract_entities_from_text(news_content)
    logger.info("Extracted entities for deduction: %s", entities)

    # Step 2 – Get graph context from KuzuDB
    graph_context = get_graph_context(kuzu_conn, entities)
    path_count = graph_context.count("\n") + 1 if graph_context.strip() else 0
    logger.info("GraphContext retrieved: %d paths", path_count)

    # Step 2b – Fallback logic: if graph context is empty
    if not graph_context.strip():
        graph_context = "注意：当前知识图谱库中暂无直接关联路径，请基于通用本体逻辑进行推演。"
        logger.info("GraphContext empty; using fallback instruction")

    # Step 3 – Build LLM service
    try:
        from app.api.routes.analysis import _get_llm_service
        llm_service = _get_llm_service()
    except Exception as exc:
        logger.warning("Could not obtain LLM service: %s", exc)
        class _StubLLM:
            def call(self, **kwargs: Any) -> str:
                return "{}"
        llm_service = _StubLLM()

    # Step 4 – Run OntologyGroundedAnalyzer
    from intelligence.grounded_analyzer import OntologyGroundedAnalyzer
    try:
        analyzer = OntologyGroundedAnalyzer(
            llm_service=llm_service,
            kuzu_conn=kuzu_conn,
        )
        result = analyzer.analyze_with_ontological_grounding(
            news_fragment=news_content,
            seed_entities=entities if entities else ["系统要素"],
            claim="此事件对现有秩序及相关实体的潜在连锁影响是什么？",
        )

        deduction: Dict[str, Any] = result.get("deduction_result", {})

        # Step 5 – Confidence boost based on graph evidence richness
        evidence_boost = 0
        if graph_context.startswith("事实:") or graph_context.startswith("推演:"):
            evidence_boost = 20
            logger.info("Graph evidence detected; applying +%d%% confidence boost", evidence_boost)

        current_conf = deduction.get("confidence", 0.5)
        boosted_conf = min(0.95, current_conf + (evidence_boost / 100.0))
        deduction["confidence"] = boosted_conf

        # Attach graph evidence for frontend display
        deduction["graph_evidence"] = graph_context
        logger.info("Deduction completed with confidence: %.2f", boosted_conf)
        return deduction

    except Exception as e:
        logger.error("Deduction failed: %s", e)
        return {
            "driving_factor": "系统暂时无法提取驱动因���",
            "scenario_alpha": "推演引擎响应异常",
            "scenario_beta": "请检查后端日志",
            "verification_gap": str(e),
            "confidence": 0.0,
            "graph_evidence": ""
        }
