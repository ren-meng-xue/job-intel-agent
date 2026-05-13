from app.tasks import celery_app


@celery_app.task(name="research.run", soft_time_limit=300)
def run_research(job_id: str, resume_id: str | None = None) -> None:
    # TODO: 调用 report_service.generate_report，完成后发布 Redis 消息 ⚠️ 风险：超时需设 soft_time_limit 并捕获异常
    raise NotImplementedError
