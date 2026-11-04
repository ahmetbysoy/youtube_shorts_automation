#!/usr/bin/env python3
"""YouTube'un herkese açık Atom akışından denetim anlık görüntüsü alır.

Bu bir tekrar koruması değildir: akış sınırlı, gecikmeli veya eksik olabilir;
özel, listelenmemiş ya da silinmiş videoları kapsadığı varsayılmamalıdır.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree

ATOM = "{http://www.w3.org/2005/Atom}"
YT = "{http://www.youtube.com/xml/schemas/2015}"
CHANNEL_RE = re.compile(r"UC[A-Za-z0-9_-]{22}\Z")
VIDEO_RE = re.compile(r"[A-Za-z0-9_-]{11}\Z")
MAX_BYTES = 2_000_000


def fetch_feed(channel_id: str) -> dict:
    if not CHANNEL_RE.fullmatch(channel_id):
        raise ValueError("Geçerli bir YouTube kanal kimliği (UC...) gerekli")
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; ChannelAudit/1.0)", "Cache-Control": "no-cache"})
    with urlopen(req, timeout=25) as response:
        data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("Akış boyut sınırını aştı")
    root = ElementTree.fromstring(data)
    if root.tag != ATOM + "feed":
        raise ValueError("Beklenen Atom akışı alınamadı")
    # YouTube bazen üst düzey yt:channelId'yi UC öneki olmadan döndürür.
    # Kanalın alternate URL'i ve her kayıt ayrı ayrı tam kimlikle doğrulanır.
    links = [x.get("href", "") for x in root.findall(ATOM + "link") if x.get("rel") == "alternate"]
    expected_link = f"https://www.youtube.com/channel/{channel_id}"
    if expected_link not in links:
        raise ValueError("Akıştaki kanal bağlantısı istenen kanalla eşleşmiyor")
    entries = []
    seen = set()
    for item in root.findall(ATOM + "entry"):
        video_id = item.findtext(YT + "videoId", default="").strip()
        owner = item.findtext(YT + "channelId", default="").strip()
        title = item.findtext(ATOM + "title", default="").strip()
        published = item.findtext(ATOM + "published", default="").strip()
        if owner != channel_id or not VIDEO_RE.fullmatch(video_id) or not title or video_id in seen:
            raise ValueError("Akışta eksik, tekrarlı veya başka kanala ait video var")
        try:
            timestamp = datetime.fromisoformat(published.replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                raise ValueError("Saat dilimi yok")
        except ValueError as exc:
            raise ValueError(f"Yayın tarihi geçersiz: {video_id}") from exc
        seen.add(video_id)
        entries.append({"video_id": video_id, "title": title, "published": published,
                        "url": f"https://www.youtube.com/watch?v={video_id}"})
    return {"channel_id": channel_id, "source": url,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "limitations": "Herkese açık Atom akışı sınırlı/gecikmeli olabilir; tüm kanal veya tüm yayın geçmişi değildir.",
            "count": len(entries), "videos": entries}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channel-id", required=True)
    args = parser.parse_args()
    try:
        result = fetch_feed(args.channel_id)
    except (OSError, HTTPError, URLError, ValueError, ElementTree.ParseError) as exc:
        print(f"Akış denetimi başarısız: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
