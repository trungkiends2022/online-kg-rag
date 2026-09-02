"""Send exactly one prompt through the configured LLM provider."""

from __future__ import annotations

import argparse

from src.llm.client import get_provider, llm_call


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", help="Prompt to send")
    parser.add_argument("--max-tokens", type=int, default=128)
    args = parser.parse_args()

    provider = get_provider()
    print(f"provider={provider.name} model={getattr(provider, 'model', 'unknown')}")
    print(llm_call(args.prompt, max_tokens=args.max_tokens))


if __name__ == "__main__":
    main()
