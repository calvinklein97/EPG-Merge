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


def normalize_name(name):
    """Bereinigt Sendernamen für den Vergleich (z.B. 'Das Erste HD' -> 'daserste')"""
    if not name:
        return ""
    name = name.lower()
    for clean_up in [" hd", " sd", " austria", " schweiz", " ch", " at", " de"]:
        name = name.replace(clean_up, "")
    return "".join(e for e in name if e.isalnum())


def merge_epgs():
    seen_channel_names = {}  # Speichert: normalized_name -> master_channel_id
    combined_channels = []
    combined_programmes = []

    print("Starte intelligenten EPG-Merge...")

    for url in EPG_URLS:
        try:
            print(f"Lade: {url}")
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                content = gzip.decompress(response.content)
                root = ET.fromstring(content)

                # Map für ID-Ersetzungen in dieser Datei
                id_map = {}

                # 1. Kanäle durchgehen & deduplizieren
                for channel in root.findall("channel"):
                    original_id = channel.get("id")

                    # Hol den ersten lesbaren Namen (display-name)
                    display_name_elem = channel.find("display-name")
                    display_name = (
                        display_name_elem.text if display_name_elem is not None else ""
                    )

                    norm_name = normalize_name(display_name)

                    if norm_name and norm_name in seen_channel_names:
                        # Sender existiert bereits! Merke dir die Master-ID
                        master_id = seen_channel_names[norm_name]
                        id_map[original_id] = master_id
                    else:
                        # Neuer Sender -> Behalten
                        if norm_name:
                            seen_channel_names[norm_name] = original_id
                        combined_channels.append(channel)

                # 2. Programme zuordnen & ID ggf. auf Master-ID umbiegen
                for programme in root.findall("programme"):
                    prog_channel = programme.get("channel")

                    # Falls dieses Programm zu einer verworfenen ID gehörte -> umleiten
                    if prog_channel in id_map:
                        programme.set("channel", id_map[prog_channel])

                    combined_programmes.append(programme)

        except Exception as e:
            print(f"Fehler bei {url}: {e}")

    # Neues Master-XML aufbauen
    tv_root = ET.Element("tv")
    for channel in combined_channels:
        tv_root.append(channel)
    for programme in combined_programmes:
        tv_root.append(programme)

    tree = ET.ElementTree(tv_root)

    output_filename = "epg.xml.gz"
    with gzip.open(output_filename, "wb") as f:
        tree.write(f, encoding="utf-8", xml_declaration=True)

    print("EPG erfolgreich zusammengeführt & dedupliziert!")


if __name__ == "__main__":
    merge_epgs()
