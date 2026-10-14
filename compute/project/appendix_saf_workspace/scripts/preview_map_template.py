#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from generate_appendix_docx import PREP_DIR, create_map_template_preview


def main() -> None:
    output_path = PREP_DIR / "appendix_map_template_preview.png"
    create_map_template_preview(output_path)
    print(output_path)


if __name__ == "__main__":
    main()
