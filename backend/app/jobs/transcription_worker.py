"""INF-02 transcription worker scaffold."""


def handle(payload: dict) -> None:
    print(f"Transcription worker received {payload}")
