"""INF-02 job queue adapter placeholder."""


def enqueue(job_type: str, payload: dict) -> None:
    print(f"Enqueued {job_type} with payload {payload}")
