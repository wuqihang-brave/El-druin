def perform_deduction(graph_context, evidence):
    """ Perform deduction based on graph context and evidence. """

    # Key improvements: 
    # (1) Fallback instruction when GraphContext is empty
    if not graph_context:
        return {
            "error": "GraphContext is empty, please provide valid context.",
            "fallback": "Consider revising the input parameters or providing more detailed context."
        }

    # (2) Dynamic confidence adjustment based on evidence richness
    base_confidence = 0.5  # Base confidence level
    evidence_count = len(evidence)  # Number of evidence pieces received
    confidence_boost = 0.2 * evidence_count  # 20% boost per evidence
    boosted_confidence = min(1.0, base_confidence + confidence_boost)

    # (3) Robust error handling returning complete JSON structure
    try:
        analysis_results = OntologyGroundedAnalyzer.analyze(graph_context, boosted_confidence)
        return {
            "success": True,
            "data": analysis_results,
            "confidence": boosted_confidence
        }
    except Exception as e:
        # (4) Detailed logging for debugging
        log_error(e)
        return {
            "success": False,
            "error": str(e),
            "confidence": boosted_confidence
        }

    # (5) Claim parameter updated
    claim = "此事件对现有秩序及相关实体的潜在连锁影响是什么？"
    
    # Logic for deduction based on the provided claim
    deduction = f"Analyzed claim: {claim} with confidence {boosted_confidence}"  # Placeholder for further logic
    return deduction