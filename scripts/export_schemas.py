"""Generate public API schemas from the strict contracts on OpenJevLXC."""

import json
from pathlib import Path

from changgeun_inference.contracts import DecisionRequest, DecisionResponse


def main() -> None:
    directory = Path(__file__).resolve().parents[1] / "shared" / "schemas"
    directory.mkdir(exist_ok=True)
    for name, model in (
        ("decision-request-1.2", DecisionRequest),
        ("decision-response-1.2", DecisionResponse),
    ):
        schema = model.model_json_schema()
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        (directory / f"{name}.json").write_text(
            json.dumps(schema, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        )
    print("API 1.2 request/response schemas generated from strict contracts")


if __name__ == "__main__":
    main()
