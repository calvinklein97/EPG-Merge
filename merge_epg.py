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
    seen_channels = set()
    seen_programmes = set()

    tv_root = ET.Element("tv")

    print("Starte optimierten Download & Merge...")

    for url in EPG_URLS:
        try:
            print(f"Lade: {url}")
            response = requests.get(url, timeout=45)
            if response.status_code == 200:
                content = gzip.decompress(response.content)
                root = ET.fromstring(content)

                # 1. Kanäle deduplizieren (nach ID)
                for channel in root.findall("channel"):
                    channel_id = channel.get("id")
                    if channel_id and channel_id not in seen_channels:
                        seen_channels.add(channel_id)
                        tv_root.append(channel)

                # 2. Sendungen deduplizieren (nach Kanal + Startzeit)
                for programme in root.findall("programme"):
                    prog_key = (
                        programme.get("channel"),
                        programme.get("start"),
                    )
                    if prog_key not in seen_programmes:
                        seen_programmes.add(prog_key)
                        tv_root.append(programme)

        except Exception as e:
            print(f"Fehler bei {url}: {e}")

    # Zusammengefügte Datei schreiben
    tree = ET.ElementTree(tv_root)
    output_filename = "epg.xml.gz"

    with gzip.open(output_filename, "wb") as f:
        tree.write(f, encoding="utf-8", xml_declaration=True)

    print("EPG erfolgreich und schlank zusammengeführt!")


if __name__ == "__main__":
    merge_epgs()
