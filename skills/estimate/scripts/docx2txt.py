#!/usr/bin/env python3
"""Extract readable text from a .docx, preserving paragraphs and table rows.

Stdlib only: a .docx is a zip with an XML document inside, which is little
enough work that a dependency isn't worth it.
"""
import sys
import zipfile
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def text_of(paragraph):
    return "".join(t.text or "" for t in paragraph.iter(W + "t"))


def indent_of(paragraph):
    """List nesting depth of a paragraph, as an integer.

    Worth the extra few lines: in an estimate, indentation is what says which
    unpriced sub-details roll up into which priced line item. Flattening it
    turns a structured breakdown into an ambiguous list.
    """
    props = paragraph.find(W + "pPr")
    if props is None:
        return 0
    numbering = props.find(W + "numPr")
    if numbering is not None:
        level = numbering.find(W + "ilvl")
        if level is not None:
            return int(level.get(W + "val", 0))
    # Fall back to a manual left indent; Word counts in twentieths of a point,
    # and 720 of those is the standard half-inch step.
    ind = props.find(W + "ind")
    if ind is not None and ind.get(W + "left"):
        return int(ind.get(W + "left")) // 720
    return 0


def extract(path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))

    lines = []
    for el in root.find(W + "body"):
        if el.tag == W + "p":
            line = text_of(el).strip()
            if line:
                lines.append("  " * indent_of(el) + line)
        elif el.tag == W + "tbl":
            for row in el.findall(W + "tr"):
                cells = [
                    " ".join(text_of(p).strip() for p in cell.findall(W + "p")).strip()
                    for cell in row.findall(W + "tc")
                ]
                lines.append(" | ".join(cells))
    return "\n".join(lines)


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: docx2txt.py <file.docx>")
    path = sys.argv[1]

    # Fail loudly rather than handing an estimator an empty spec. There is no
    # stdlib PDF text extractor, and a silent empty string reads downstream as
    # "the spec says nothing" instead of "we could not read the spec".
    if not path.lower().endswith(".docx"):
        sys.exit(
            f"{path}: only .docx is supported (legacy .doc and .pdf are not). "
            "Convert it to .docx, or paste the spec text directly."
        )

    try:
        print(extract(path))
    except (zipfile.BadZipFile, KeyError) as e:
        sys.exit(f"{path}: not a readable .docx ({e})")


if __name__ == "__main__":
    main()
