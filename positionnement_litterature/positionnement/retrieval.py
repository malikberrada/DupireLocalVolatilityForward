"""Optional public retrieval; metadata candidates never become reviewed evidence."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import urlencode
from urllib.request import Request,urlopen


def fetch(url,timeout=10,max_bytes=20000000):
    if not url.startswith("https://"):raise ValueError("Only HTTPS sources are supported")
    req=Request(url,headers={"User-Agent":"DupireLiteraturePositioning/0.1 (research; no automatic novelty scoring)"})
    start=time.monotonic();chunks=[];size=0
    with urlopen(req,timeout=timeout) as response:
        final=response.geturl()
        if not final.startswith("https://"):raise ValueError("Insecure redirect refused")
        while True:
            if time.monotonic()-start>3*timeout:raise TimeoutError("Source transfer exceeded its time budget")
            block=response.read(min(65536,max_bytes-size+1))
            if not block:break
            chunks.append(block);size+=len(block)
            if size>max_bytes:raise ValueError("Source exceeds size limit")
        mime=response.headers.get("Content-Type","")
    data=b"".join(chunks)
    wall=data[:30000].lower()
    if any(marker in wall for marker in (b"access denied",b"just a moment...",b"verify you are human")):
        raise ValueError("Access wall detected; no full-text evidence created")
    return data,{"url":url,"final_url":final,"content_type":mime,"size_bytes":size,
                 "sha256":hashlib.sha256(data).hexdigest(),"fetched_utc":datetime.now(timezone.utc).isoformat()}


def fetch_sources(registry,out,progress):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);manifest=[]
    for paper in registry["papers"]:
        progress.event("Download primary source",force=True,paper=paper["id"])
        try:
            data,record=fetch(paper.get("fetch_url",paper["url"]))
            suffix=".pdf" if data.startswith(b"%PDF") else ".html"
            path=out/(paper["id"]+suffix);path.write_bytes(data)
            record.update(id=paper["id"],status="downloaded",path=path.name,
                          annotation_access_not_upgraded_automatically=True)
        except Exception as exc:
            record={"id":paper["id"],"url":paper["url"],"status":"not_downloaded","reason":str(exc)}
        manifest.append(record)
        (out/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    return manifest


def crossref_candidates(query,cutoff,rows=10):
    if not 1<=rows<=50:raise ValueError("Crossref rows must be in [1,50]")
    params={"query.bibliographic":query,"rows":rows,"filter":"until-pub-date:"+cutoff}
    data,transfer=fetch("https://api.crossref.org/works?"+urlencode(params),max_bytes=2000000)
    payload=json.loads(data)
    entries=[]
    for item in payload["message"]["items"]:
        entries.append({"title":item.get("title",[]),"doi":item.get("DOI"),"url":item.get("URL"),
                        "published":item.get("published"),"status":"unreviewed_candidate"})
    return {"query":query,"cutoff":cutoff,"retrieval":transfer,"candidates":entries,
            "coverage":"Crossref metadata only; not an exhaustive search or a full-text theorem review"}
