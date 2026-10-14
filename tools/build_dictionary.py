#!/usr/bin/env python3
"""Build an offline JavaScript dictionary from the official FreeDict TEI source."""
import json
import sys
import tarfile
import xml.etree.ElementTree as ET
from pathlib import Path

ARCHIVE = Path(sys.argv[1])
OUTPUT = Path(sys.argv[2])

def local(tag):
    return tag.rsplit("}", 1)[-1]

def clean(element):
    return " ".join("".join(element.itertext()).split())

with tarfile.open(ARCHIVE, "r:xz") as archive:
    members = [m for m in archive.getmembers() if m.isfile() and m.name.lower().endswith(".tei")]
    if not members:
        raise SystemExit("FreeDict archive did not contain a TEI dictionary file.")
    source = archive.extractfile(members[0])
    if source is None:
        raise SystemExit("Could not read the FreeDict TEI file.")
    root = ET.parse(source).getroot()

entries = {}
for entry in root.iter():
    if local(entry.tag) != "entry":
        continue
    form = next((child for child in entry if local(child.tag) == "form"), None)
    if form is None:
        continue
    orth = next((el for el in form.iter() if local(el.tag) == "orth"), None)
    if orth is None:
        continue
    headword = clean(orth)
    if not headword or len(headword) > 100:
        continue

    translations = []
    for citation in entry.iter():
        if local(citation.tag) == "cit" and citation.attrib.get("type") == "trans":
            quote = next((child for child in citation if local(child.tag) == "quote"), None)
            if quote is not None:
                value = clean(quote)
                if value and value not in translations:
                    translations.append(value)
    if not translations:
        for definition in entry.iter():
            if local(definition.tag) == "def":
                value = clean(definition)
                if value and value not in translations:
                    translations.append(value)
    if not translations:
        continue

    pron_el = next((el for el in form.iter() if local(el.tag) == "pron"), None)
    pron = clean(pron_el) if pron_el is not None else ""
    key = headword.casefold()
    if key not in entries:
        entries[key] = {"it": headword, "pt": [], "pron": pron}
    for value in translations:
        if value not in entries[key]["pt"]:
            entries[key]["pt"].append(value)
    if not entries[key]["pron"] and pron:
        entries[key]["pron"] = pron

result = []
for item in sorted(entries.values(), key=lambda x: x["it"].casefold()):
    translation = "; ".join(item["pt"][:12])[:500]
    result.append([item["it"], translation, item["pron"], ""])

if len(result) < 5000:
    raise SystemExit(f"Expected at least 5,000 entries; parsed only {len(result)}.")

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
payload = "/* FreeDict/WikDict Italian–Portuguese, release 2025.11.23. CC BY-SA 3.0. https://freedict.org/ */\n"
payload += "window.freedictEntries = " + json.dumps(result, ensure_ascii=False, separators=(",", ":")) + ";\n"
OUTPUT.write_text(payload, encoding="utf-8")
print(f"Prepared {len(result)} unique Italian–Portuguese entries for the offline app.")
