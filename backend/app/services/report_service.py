"""Deprecated report service compatibility module.

Report generation now runs through the LangGraph research flow in
`app.graphs.research_graph` and is launched by `app.tasks.research.task_run_research`.
This module is kept only to make accidental legacy imports fail with a clear message.
"""


async def generate_report(job_id: str, resume_id: str | None = None) -> dict:
    raise RuntimeError(
        "generate_report() is deprecated. Use task_run_research(job_id) and "
        "app.graphs.research_graph.get_research_graph() instead."
    )
