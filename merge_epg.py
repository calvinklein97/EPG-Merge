import gzip
import logging
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


def fetch_source(url: str) -> ET.Element | None:
    """Lädt und parsed eine EPG-Quelle. Gibt None zurück bei Fehler,
    statt den kompletten Merge lautlos zu verfälschen."""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        content = gzip.decompress(response.content)
        return ET.fromstring(content)
    except Exception as e:
        log.warning(f"  -> Quelle übersprungen wegen Fehler: {url} ({e})")
        return None


def dedupe_channels(sources: list[ET.Element]) -> tuple[list[ET.Element], set[str]]:
    """Dedupliziert Kanäle rein anhand der ID (nachweislich kollisionsfrei
    über alle epgshare-Quellen, da diese Länder-Suffixe wie .de/.at/.ch
    vergeben). Kanäle ohne id werden übersprungen und geloggt."""
    seen_ids = set()
    result = []
    skipped_no_id = 0
    skipped_dupe = 0

    for root in sources:
        for channel in root.findall("channel"):
            cid = channel.get("id")
            if not cid:
                skipped_no_id += 1
                continue
            if cid in seen_ids:
                skipped_dupe += 1
                continue
            seen_ids.add(cid)
            result.append(channel)

    if skipped_no_id:
        log.info(f"  -> {skipped_no_id} Kanäle ohne id übersprungen")
    if skipped_dupe:
        log.info(f"  -> {skipped_dupe} echte ID-Duplikate entfernt")

    return result, seen_ids


def dedupe_programmes(sources: list[ET.Element], valid_channel_ids: set[str]) -> list[ET.Element]:
    """Entfernt (a) verwaiste Programme ohne zugehörigen Kanal und
    (b) exakte Duplikate (gleicher Kanal + Start + Stop + Titel)."""
    seen_keys = set()
    result = []
    skipped_orphan = 0
    skipped_dupe = 0

    for root in sources:
        for programme in root.findall("programme"):
            ch_ref = programme.get("channel")

            if ch_ref not in valid_channel_ids:
                skipped_orphan += 1
                continue

            title_el = programme.find("title")
            title_text = title_el.text if title_el is not None else ""
            key = (ch_ref, programme.get("start"), programme.get("stop"), title_text)

            if key in seen_keys:
                skipped_dupe += 1
                continue

            seen_keys.add(key)
            result.append(programme)

    if skipped_orphan:
        log.info(f"  -> {skipped_orphan} verwaiste Programme (ohne gültigen Kanal) entfernt")
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
        log.error("Keine einzige Quelle erfolgreich geladen – breche ab, kein Output geschrieben.")
        return

    combined_channels, valid_ids = dedupe_channels(parsed_sources)
    combined_programmes = dedupe_programmes(parsed_sources, valid_ids)

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
