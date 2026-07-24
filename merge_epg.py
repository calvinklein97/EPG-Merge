import gzip
import requests
import xml.etree.ElementTree as ET

# Deine EPG-Quellen von epgshare01 (oder anderen Anbietern)
EPG_URLS = [
    "https://epgshare01.online/epgshare01/epg_ripper_DE1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_AT1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_CH1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_FR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_RAKUTEN.xml.gz",
]


def merge_epgs():
    combined_channels = []
    combined_programmes = []

    print("Starte Download und Merge...")

    for url in EPG_URLS:
        try:
            print(f"Lade: {url}")
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                # Entpacken und Parsen der XML
                content = gzip.decompress(response.content)
                root = ET.fromstring(content)

                for channel in root.findall("channel"):
                    combined_channels.append(channel)
                for programme in root.findall("programme"):
                    combined_programmes.append(programme)
        except Exception as e:
            print(f"Fehler bei {url}: {e}")

    # Neues Master-XML erstellen
    tv_root = ET.Element("tv")

    for channel in combined_channels:
        tv_root.append(channel)
    for programme in combined_programmes:
        tv_root.append(programme)

    tree = ET.ElementTree(tv_root)

    # In komprimierte XML.GZ schreiben
    output_filename = "epg.xml.gz"
    with gzip.open(output_filename, "wb") as f:
        tree.write(f, encoding="utf-8", xml_declaration=True)

    print("EPG erfolgreich zusammengeführt!")


if __name__ == "__main__":
    merge_epgs()
