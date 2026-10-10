import json
import os
import re
import time
from pathlib import Path

import requests

BASE="https://api.notion.com/v1"
ROOT="3f5547fd-c285-8181-96d2-f1f56adb72e7"
HEAD={"Authorization":"Bearer "+os.environ["NOTION_API_KEY"],"Notion-Version":"2022-06-28"}
SESSION=requests.Session()
SESSION.headers.update(HEAD)

def children(pid):
    result=[]
    cursor=None
    while True:
        params={"page_size":100}
        if cursor:
            params["start_cursor"]=cursor
        response=SESSION.get(f"{BASE}/blocks/{pid}/children",params=params,timeout=35)
        response.raise_for_status()
        data=response.json()
        result+=data["results"]
        if not data.get("has_more"):
            return result
        cursor=data["next_cursor"]

def plain(block):
    obj=block.get(block.get("type",""),{})
    return "".join(t.get("plain_text",t.get("text",{}).get("content","")) for t in obj.get("rich_text",[]))

def location_query(title,blocks):
    lines=[]
    for block in blocks:
        lines+=plain(block).splitlines()
    # Only geocode an explicit destination or an identifiable place in the title.
    for line in lines:
        m=re.search(r"(?:^|\*\*)\s*(?:Ort|Standort|Adresse|Zielort)\s*:?\s*(?:\*\*)?\s*(.+)",line,re.I)
        if m:
            candidate=m.group(1).strip(" *-:")
            if "nicht ermittelt" not in candidate.lower() and len(candidate)>3:
                return candidate[:180]
    # If the title contains a distinctive geographic name, geocoder may resolve it.
    return re.sub(r"\s+[–-]\s+.*$","",title).strip()[:100]

def geocode(query):
    response=requests.get("https://nominatim.openstreetmap.org/search",params={"q":query,"format":"json","limit":1,"addressdetails":0},headers={"User-Agent":"NotionAusflugszieleMap/1.0 (personal hobby project; github.com/Chevy4170/notion-video-archiv)","Accept-Language":"de"},timeout=30)
    response.raise_for_status()
    results=response.json()
    if not results:
        return None
    found=results[0]
    return {"lat":float(found["lat"]),"lon":float(found["lon"])}

def build():
    points=[]
    for block in children(ROOT):
        if block.get("type")!="child_page":
            continue
        title=block["child_page"]["title"]
        if title=="Karte":
            continue
        entry=children(block["id"])
        query=location_query(title,entry)
        if not query:
            continue
        try:
            coords=geocode(query)
        except Exception as exc:
            print("Geocoding fehlgeschlagen:",title,str(exc)[:160],flush=True)
            coords=None
        time.sleep(1.1)
        if not coords:
            print("Kein eindeutiger Standort:",title,query,flush=True)
            continue
        points.append({"title":title,"url":"https://www.notion.so/"+block["id"].replace("-",""),**coords})
        print("Karten-Pin:",title,query,flush=True)
    template=Path("map-template.html").read_text(encoding="utf-8")
    data=json.dumps(points,ensure_ascii=False).replace("<","\\u003c")
    output=template.replace("/*MAP_DATA*/[]",data)
    Path("site").mkdir(exist_ok=True)
    Path("site/index.html").write_text(output,encoding="utf-8")
    print("Karte erstellt, Pins:",len(points),flush=True)

if __name__=="__main__":
    build()
