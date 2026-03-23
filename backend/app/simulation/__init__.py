"""
Multi-agent simulation package (LangGraph-backed).

Public surface::

    from app.simulation.runner import SimulationRunner
    result = SimulationRunner().run(news_event="...", max_steps=8)
"""

from app.simulation.runner import SimulationRunner  # noqa: F401

__all__ = ["SimulationRunner"]
