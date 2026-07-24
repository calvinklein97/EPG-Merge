import gzip
import logging
import re
import xml.etree.ElementTree as ET

import requests

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("epg-merge")

EPG_URLS = [
    "https://epgshare01.online/epgshare01/epg_ripper_DE1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_AT1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_CH1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_FR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_RAKUTEN.xml.gz",
]

# Reihenfolge oben = Priorität. Bei einem Namens-Merge wird der Kanal aus der
# zuerst geladenen Quelle als "kanonisch" behalten (also DE1 vor AT1 vor CH1...).

PLACEHOLDER_PATTERN = re.compile(r"\((logo|vod|platzhalter|placeholder)", re.IGNORECASE)


def normalize_name(name: str) -> str | None:
    """Normalisiert einen Kanalnamen für den Vergleich über Quellen hinweg.

    Gibt None zurück für Kanäle, die NIE automatisch mit anderen gemergt
    werden sollen (z.B. "Sky Cinema (Logo VOD)" - Platzhalter-/VOD-Kanäle,
    die trotz ähnlichem Namen inhaltlich etwas anderes sind).

    WICHTIG: '+' wird bewusst NICHT entfernt, da z.B. "EU Parliament" und
    "EU Parliament+" oder "Disney" und "Disney+" reale, unterschiedliche
    Kanäle sein können. Wird zu aggressiv normalisiert, entsteht wieder
    das ursprüngliche "Sky Sport 3"-Problem, nur in die andere Richtung.
    """
    if not name:
        return None
    n = name.strip().lower()

    if PLACEHOLDER_PATTERN.search(n):
        return None

    n = re.sub(r"\(ard\)|\(zdf\)", "", n)   # bekannte harmlose Sender-Zusätze
    n = re.sub(r"[.\-_]+", " ", n)          # Punkt/Bindestrich -> Leerzeichen
    n = re.sub(r"[^a-z0-9äöüß+ ]+", "", n)  # Rest weg, '+' bleibt erhalten
    n = re.sub(r"\s+", " ", n).strip()
    return n or None


def get_display_name(channel_elem) -> str:
    dn = channel_elem.find("display-name")
    if dn is not None and dn.text:
        return dn.text.strip()
    return channel_elem.get("id", "")


def fetch_source(url: str) -> ET.Element | None:
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        content = gzip.decompress(response.content)
        return ET.fromstring(content)
    except Exception as e:
        log.warning(f"  -> Quelle übersprungen wegen Fehler: {url} ({e})")
        return None


def merge_channels(sources: list[ET.Element]) -> tuple[list[ET.Element], dict[str, str]]:
    """Dedupliziert Kanäle in zwei Stufen:
    1. Exakte ID-Duplikate (kollisionsfrei laut Datenanalyse, aber als
       Sicherheitsnetz falls sich das Format von epgshare mal ändert).
    2. Kanäle mit exakt gleichem normalisiertem Anzeigenamen über
       verschiedene Quellen hinweg (z.B. "Das Erste" in DE1/AT1/CH1/FR1).

    Gibt zurück: (finale Kanalliste, id_remap)
    id_remap bildet JEDE ursprünglich gesehene id auf die im Ergebnis
    tatsächlich verwendete (kanonische) id ab - wird gebraucht, um die
    <programme>-Referenzen korrekt umzuschreiben.
    """
    seen_ids: set[str] = set()
    name_to_canonical_id: dict[str, str] = {}
    id_remap: dict[str, str] = {}
    result: list[ET.Element] = []

    stats = {"no_id": 0, "exact_id_dupe": 0, "name_merge": 0}

    for root in sources:
        for channel in root.findall("channel"):
            cid = channel.get("id")
            if not cid:
                stats["no_id"] += 1
                continue

            if cid in seen_ids:
                # Exaktes ID-Duplikat (identische ID, evtl. verschiedene Quelle)
                stats["exact_id_dupe"] += 1
                continue

            name = get_display_name(channel)
            norm = normalize_name(name)

            if norm is not None and norm in name_to_canonical_id:
                # Gleicher Kanal (nach Namen), andere Quelle -> mergen
                canonical_id = name_to_canonical_id[norm]
                id_remap[cid] = canonical_id
                seen_ids.add(cid)
                stats["name_merge"] += 1
                continue

            # Neuer, eigenständiger Kanal
            seen_ids.add(cid)
            id_remap[cid] = cid
            if norm is not None:
                name_to_canonical_id[norm] = cid
            result.append(channel)

    if stats["no_id"]:
        log.info(f"  -> {stats['no_id']} Kanäle ohne id übersprungen")
    if stats["exact_id_dupe"]:
        log.info(f"  -> {stats['exact_id_dupe']} exakte ID-Duplikate entfernt")
    if stats["name_merge"]:
        log.info(f"  -> {stats['name_merge']} Kanäle über Namensgleichheit zusammengeführt")

    return result, id_remap


def merge_programmes(sources: list[ET.Element], id_remap: dict[str, str]) -> list[ET.Element]:
    """Schreibt Programme auf die kanonische Kanal-ID um und entfernt
    (a) verwaiste Programme ohne gültigen Kanal und
    (b) exakte Duplikate (gleicher Kanal + Start + Stop + Titel)."""
    seen_keys = set()
    result = []
    skipped_orphan = 0
    skipped_dupe = 0

    for root in sources:
        for programme in root.findall("programme"):
            ch_ref = programme.get("channel")
            canonical_id = id_remap.get(ch_ref)

            if canonical_id is None:
                skipped_orphan += 1
                continue

            if canonical_id != ch_ref:
                programme.set("channel", canonical_id)

            title_el = programme.find("title")
            title_text = title_el.text if title_el is not None else ""
            key = (canonical_id, programme.get("start"), programme.get("stop"), title_text)

            if key in seen_keys:
                skipped_dupe += 1
                continue

            seen_keys.add(key)
            result.append(programme)

    if skipped_orphan:
        log.info(f"  -> {skipped_orphan} verwaiste Programme entfernt")
    if skipped_dupe:
        log.info(f"  -> {skipped_dupe} exakte Programm-Duplikate entfernt")

    return result


def merge_epgs():
    log.info("Starte EPG-Merge...")

    parsed_sources = []
    for url in EPG_URLS:
        log.info(f"Lade: {url}")
        root = fetch_source(url)
        if root is not None:
            parsed_sources.append(root)

    if not parsed_sources:
        log.error("Keine einzige Quelle erfolgreich geladen - breche ab, kein Output geschrieben.")
        return

    combined_channels, id_remap = merge_channels(parsed_sources)
    combined_programmes = merge_programmes(parsed_sources, id_remap)

    tv_root = ET.Element("tv")
    for channel in combined_channels:
        tv_root.append(channel)
    for programme in combined_programmes:
        tv_root.append(programme)

    tree = ET.ElementTree(tv_root)
    output_filename = "epg.xml.gz"
    with gzip.open(output_filename, "wb") as f:
        tree.write(f, encoding="utf-8", xml_declaration=True)

    log.info(
        f"Fertig: {len(combined_channels)} Kanäle, {len(combined_programmes)} Programme "
        f"aus {len(parsed_sources)}/{len(EPG_URLS)} Quellen."
    )


if __name__ == "__main__":
    merge_epgs()
