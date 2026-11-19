#!/usr/bin/env python3
"""Map push refs without silently changing Git tags or claiming reserved latest."""
import os
import re
import sys


def image_ref(repository: str, ref: str) -> str:
    if ref == "refs/heads/main":
        tag = "latest"
    elif ref.startswith("refs/heads/"):
        tag = ref.removeprefix("refs/heads/").replace("/", "-")
    elif ref.startswith("refs/tags/"):
        tag = ref.removeprefix("refs/tags/")
    else:
        raise ValueError(f"Unsupported Git ref: {ref}")
    if tag == "latest" and ref != "refs/heads/main":
        raise ValueError("latest is reserved for pushes to branch main")
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}", tag, flags=re.ASCII):
        raise ValueError(f"Invalid Docker tag: {tag!r}; only branch '/' is converted to '-'")
    repository = repository.lower()
    if not re.fullmatch(r"[a-z0-9_.-]+/[a-z0-9_.-]+", repository):
        raise ValueError("Expected GitHub owner/repository")
    return f"ghcr.io/{repository}:{tag}"


if __name__ == "__main__":
    try:
        value = image_ref(os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_REF"])
        print(value)
        if output := os.environ.get("GITHUB_OUTPUT"):
            with open(output, "a", encoding="utf-8") as stream:
                stream.write(f"image={value}\n")
    except (KeyError, ValueError) as error:
        print(f"::error::{error}", file=sys.stderr)
        sys.exit(1)
