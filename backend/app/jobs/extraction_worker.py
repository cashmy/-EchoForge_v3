"""INF-02 extraction worker scaffold."""


def handle(payload: dict) -> None:
    print(f"Extraction worker received {payload}")
