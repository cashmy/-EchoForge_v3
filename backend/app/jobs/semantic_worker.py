"""INF-02 semantic worker scaffold."""


def handle(payload: dict) -> None:
    print(f"Semantic worker received {payload}")
