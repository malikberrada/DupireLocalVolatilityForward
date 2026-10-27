"""Optional empirical I/O. No US equity/ETF substitution for European indices."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import csv
import json
import re
import time
import numpy as np
from .data import Quotes
from .progress import atomic_json

EUROPEAN_CANDIDATES={"^SPX":"Cboe SPX/SPXW; verify the actual series and settlement",
                     "^XSP":"Cboe XSP; verify the actual series and settlement"}


def snapshot(symbols,out,progress,max_expiries=12,retries=3,rps=.5,
             expiry_selection="front",min_days=None,max_days=None,require_matched_pairs=0):
    import yfinance as yf
    if not 0<rps<=2 or retries<1 or max_expiries<1:
        raise ValueError("Require 0<rps<=2, retries>=1, max_expiries>=1")
    if not symbols or any(s not in EUROPEAN_CANDIDATES for s in symbols):
        raise ValueError("Empirical universe is ^SPX,^XSP; arbitrary American contracts are not admitted")
    if require_matched_pairs < 0 or require_matched_pairs == 1:
        raise ValueError("require-matched-pairs must be 0 (disabled) or >=2")
    from .market_quality import select_expiries,audit_file
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    archive={"started_utc":datetime.now(timezone.utc).isoformat(),"source":"yfinance",
             "quote_timestamps_available":False,"chains":[],"errors":[],
             "warning":"Snapshot times are retrieval times. lastTradeDate is NOT a bid/ask timestamp."}
    archive["expiry_selection"]={"mode":expiry_selection,"min_days":min_days,"max_days":max_days,
                                 "max_expiries_per_symbol":max_expiries,"symbols":{}}
    next_request=0.
    def request(fn,label):
        nonlocal next_request
        for attempt in range(1,retries+1):
            delay=max(0.,next_request-time.monotonic())
            if delay:
                progress.event(label,force=True,state="rate_limit",wait_seconds=round(delay,2))
                time.sleep(delay)
            try:
                with progress.phase(label,attempt=attempt,total_attempts=retries):
                    result=fn()
                next_request=time.monotonic()+1/rps
                return result
            except Exception as e:
                next_request=time.monotonic()+max(1/rps,min(2**attempt,15))
                progress.event(label,force=True,state="retry",attempt=attempt,error=str(e))
                if attempt==retries:
                    raise
    for symbol in progress.bar(symbols,desc="European index candidates"):
        ticker=yf.Ticker(symbol)
        try:
            expiries=request(lambda:list(ticker.options),symbol+" expiries")
            if not expiries:
                raise ValueError("Yahoo returned no option expiries; no fallback instrument used")
        except Exception as e:
            archive["errors"].append({"symbol":symbol,"error":str(e)})
            atomic_json(out/"snapshot.json",archive)
            continue
        selected=select_expiries(expiries,max_expiries,expiry_selection,min_days,max_days,archive["started_utc"])
        archive["expiry_selection"]["symbols"][symbol]={"available_count":len(expiries),"selected":selected}
        for expiry in progress.bar(selected,desc=symbol+" option chains"):
            start=datetime.now(timezone.utc).isoformat()
            try:
                chain=request(lambda:ticker.option_chain(expiry),f"{symbol} {expiry}")
                # DataFrame.to_json preserves columns and emits ISO trade times.
                calls=json.loads(chain.calls.to_json(orient="records",date_format="iso"))
                puts=json.loads(chain.puts.to_json(orient="records",date_format="iso"))
                archive["chains"].append({"symbol":symbol,"expiry":expiry,"retrieval_started_utc":start,
                                           "retrieval_ended_utc":datetime.now(timezone.utc).isoformat(),
                                           "calls":calls,"puts":puts})
            except Exception as e:
                archive["errors"].append({"symbol":symbol,"expiry":expiry,"error":str(e)})
            atomic_json(out/"snapshot.json",archive)
    archive["ended_utc"]=datetime.now(timezone.utc).isoformat()
    atomic_json(out/"snapshot.json",archive)
    if not archive["chains"]:
        raise RuntimeError(f"No European option chain available. Details saved to {out/'snapshot.json'}. Synthetic experiments remain available.")
    quality=audit_file(out/"snapshot.json",out/"snapshot.quality.json",max(2,require_matched_pairs or 3))
    for row in quality["roots"]:
        progress.event("Downloaded book quality",force=True,state="assessed",**row)
    if require_matched_pairs and not quality["has_enough_paired_books"]:
        progress.event("snapshot",force=True,state="no_paired_books",report=str(out/"snapshot.quality.json"))
        raise SystemExit(3)
    return archive


def normalize_snapshot(snapshot_path,curves_path,symbol,root,out):
    """One root/settlement family per run. F,D,T supplied explicitly per expiry.

    Fixing estimated F and D is a conditional analysis; uncertainty is NOT
    silently propagated by this function. No spot=forward substitution.
    """
    # Estimated curves carry their full A=D*F,D feasible set. Never quietly
    # downgrade one to a manually verified point normalization.
    sidecar=Path(str(curves_path)+".uncertainty.json")
    if sidecar.exists():
        from .curve_estimation import normalize_estimated
        return normalize_estimated(snapshot_path,curves_path,symbol,root,out)
    if symbol not in EUROPEAN_CANDIDATES or not re.fullmatch(r"[A-Z]+",root):
        raise ValueError("Select an allowed European index and an explicit option root, e.g. SPXW")
    archive=json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
    with Path(curves_path).open(newline="",encoding="utf-8-sig") as f:
        rows=list(csv.DictReader(f))
    if any(r.get("source")=="estimated_call_put_intervals" for r in rows):
        raise ValueError("Estimated curves require their .uncertainty.json certificate alongside the CSV")
    curves={}
    for r in rows:
        if r.get("symbol")!=symbol or r.get("root")!=root:
            continue
        if r.get("style","").lower()!="european" or not r.get("settlement"):
            raise ValueError("Each curve row needs verified style=european and an explicit settlement label")
        if r["expiry"] in curves:
            raise ValueError("Duplicate normalization curve row for the same root/expiry")
        vals=[float(r[k]) for k in ("time","forward","discount")]
        if not np.isfinite(vals).all() or min(vals)<=0:
            raise ValueError("Require positive finite time, forward and discount")
        curves[r["expiry"]]=(vals,r["settlement"])
    data=[];excluded=[];used=[]
    for chain in archive.get("chains",[]):
        if chain["symbol"]!=symbol:
            continue
        selected=[]
        for r in chain.get("calls",[]):
            m=re.match(r"^([A-Z]+)\d{6}[CP]\d{8}$",r.get("contractSymbol", ""))
            if m and m.group(1)==root:
                selected.append(r)
        if not selected:
            continue
        if chain["expiry"] not in curves:
            raise ValueError(f"Missing verified F,D,T curve for {root} {chain['expiry']}")
        (T,F,D),settlement=curves[chain["expiry"]]
        used.append({"expiry":chain["expiry"],"time":T,"forward":F,"discount":D,"settlement":settlement})
        for r in selected:
            values=[r.get(k) for k in ("strike","bid","ask")]
            if any(v is None for v in values) or not np.isfinite(np.asarray(values,float)).all():
                excluded.append({"contract":r.get("contractSymbol"),"reason":"missing/nonfinite book"});continue
            K,b,a=map(float,values)
            if K<=0 or b<0 or a<=0:
                excluded.append({"contract":r.get("contractSymbol"),"reason":"nonpositive strike/ask or negative bid"});continue
            # Retain crossed quotes: they may explain an F0 failure.
            data.append([T,K/F,b/(D*F),a/(D*F)])
    if not data:
        raise ValueError("No matching usable call quotes for this symbol/root")
    a=np.asarray(data)
    q=Quotes(a[:,0],a[:,1],a[:,2],a[:,3])
    q.write(out)
    atomic_json(str(out)+".metadata.json",{"symbol":symbol,"root":root,"normalization_curves":used,
                "excluded":excluded,"quote_count":len(data),"quotes_sha256":q.digest(),
                "forward_discount_uncertainty_propagated":False,"conditional_on_supplied_normalization":True,
                "synchronized_bid_ask_not_certified":True,"snapshot":str(snapshot_path)})
    return q

