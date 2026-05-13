async def generate_report(job_id: str, resume_id: str | None = None) -> dict:
    # TODO: 串联 crawler → search → llm，依次生成 6 模块内容 ⚠️ 风险：LLM 链路耗时长，需分步推 SSE 进度
    raise NotImplementedError
