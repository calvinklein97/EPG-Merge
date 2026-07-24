import gzip
import re
import xml.etree.ElementTree as ET
import requests

EPG_URLS = [
    "https://epgshare01.online/epgshare01/epg_ripper_DE1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_AT1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_CH1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_FR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_RAKUTEN.xml.gz",
]


def normalize_name(name):
    """Sichere Normalisierung: Entfernt nur HD/SD/Länder-Suffixe am ENDE des Namens."""
    if not name:
        return ""

    # In Kleinbuchstaben umwandeln und Leerzeichen normieren
    cleaned = name.lower().strip()

    # Nur Anhänge GANZTÄGIG am Ende des Namens entfernen (mit Wortgrenze)
    suffixes_to_remove = [
        r"\bhd\b",
        r"\bsd\b",
        r"\baustria\b",
        r"\bschweiz\b",
        r"\bat\b",
        r"\bch\b",
        r"\bde\b",
    ]

    for pattern in suffixes_to_remove:
        cleaned = re.sub(pattern, "", cleaned).strip()

    # Nur Sonderzeichen/Mehrfach-Leerzeichen entfernen, Zahlen BLEIBEN ERHALTEN
    cleaned = re.sub(r"[^\w\s]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned


def merge_epgs():
    seen_channel_names = {}  # norm_name -> master_channel_id
    combined_channels = []
    combined_programmes = []

    print("Starte präzisen EPG-Merge...")

    for url in EPG_URLS:
        try:
            print(f"Lade: {url}")
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                content = gzip.decompress(response.content)
                root = ET.fromstring(content)

                id_map = {}

                # 1. Kanäle verarbeiten
                for channel in root.findall("channel"):
                    original_id = channel.get("id")

                    display_name_elem = channel.find("display-name")
                    display_name = (
                        display_name_elem.text if display_name_elem is not None else ""
                    )

                    norm_name = normalize_name(display_name)

                    if norm_name and norm_name in seen_channel_names:
                        # Bereits vorhanden -> Verwenden den ersten als Master
                        master_id = seen_channel_names[norm_name]
                        id_map[original_id] = master_id
                    else:
                        # Neuer, einzigartiger Sender
                        if norm_name:
                            seen_channel_names[norm_name] = original_id
                        combined_channels.append(channel)

                # 2. Programme verarbeiten
                for programme in root.findall("programme"):
                    prog_channel = programme.get("channel")
                    if prog_channel in id_map:
                        programme.set("channel", id_map[prog_channel])
                    combined_programmes.append(programme)

        except Exception as e:
            print(f"Fehler bei {url}: {e}")

    # Neues XML zusammenbauen
    tv_root = ET.Element("tv")
    for channel in combined_channels:
        tv_root.append(channel)
    for programme in combined_programmes:
        tv_root.append(programme)

    tree = ET.ElementTree(tv_root)

    output_filename = "epg.xml.gz"
    with gzip.open(output_filename, "wb") as f:
        tree.write(f, encoding="utf-8", xml_declaration=True)

    print("EPG erfolgreich zusammengeführt! Sky Sport Feeds sollten jetzt alle da sein.")


if __name__ == "__main__":
    merge_epgs()
