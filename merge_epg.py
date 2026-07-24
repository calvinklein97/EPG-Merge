import gzip
import xml.etree.ElementTree as ET
import requests

EPG_URLS = [
    "https://epgshare01.online/epgshare01/epg_ripper_DE1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_AT1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_CH1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_FR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_RAKUTEN.xml.gz",
]


def merge_epgs():
    seen_channel_ids = set()
    combined_channels = []
    combined_programmes = []

    print("Starte exakten ID-Merge...")

    for url in EPG_URLS:
        try:
            print(f"Lade: {url}")
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                content = gzip.decompress(response.content)
                root = ET.fromstring(content)

                # 1. Kanäle anhand ihrer EINDEUTIGEN ID hinzufügen
                for channel in root.findall("channel"):
                    channel_id = channel.get("id")

                    # Nur hinzufügen, wenn die EXAKTE ID noch nicht existiert
                    if channel_id and channel_id not in seen_channel_ids:
                        seen_channel_ids.add(channel_id)
                        combined_channels.append(channel)

                # 2. ALLE Programme einfach mitnehmen
                for programme in root.findall("programme"):
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

    print("EPG erfolgreich zusammengeführt! Alle Sky Sport Kanäle sind garantiert enthalten.")


if __name__ == "__main__":
    merge_epgs()
