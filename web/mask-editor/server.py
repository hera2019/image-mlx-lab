#!/usr/bin/env python3
import base64, json, re, subprocess, time, urllib.error, urllib.request
from datetime import datetime
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PORT = 18080
QWEN_BASE = "http://127.0.0.1:11234"
QWEN_API = QWEN_BASE + "/v1/images/generations"
PERF_DIR = ROOT / "results" / "performance"
PERF_LOG = PERF_DIR / "qwen-workbench.jsonl"
OUT_DIR = ROOT / "results" / "web"
LIB_DIR = ROOT / "results" / "library"
INTERMEDIATE_DIR = ROOT / "results" / "intermediate"
IMAGE_EXTS = {".png",".jpg",".jpeg",".webp"}

def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")

def proc_rss_mb():
    try:
        pids=subprocess.check_output(["pgrep","-f","mlx-serve.*--port 11234"],text=True).strip().splitlines()
        if not pids: return None
        rss=subprocess.check_output(["ps","-o","rss=","-p",pids[0]],text=True).strip()
        return round(int(rss)/1024,1)
    except Exception: return None

def swap_used_mb():
    try:
        s=subprocess.check_output(["sysctl","-n","vm.swapusage"],text=True)
        m=re.search(r"used\s*=\s*([0-9.]+)M",s)
        return float(m.group(1)) if m else None
    except Exception: return None

def memory_free_pct():
    try:
        s=subprocess.check_output(["memory_pressure"],text=True,timeout=3)
        m=re.search(r"System-wide memory free percentage:\s*([0-9]+)%",s)
        return int(m.group(1)) if m else None
    except Exception: return None

def decoded_size(v):
    try: return len(base64.b64decode(v,validate=False))
    except Exception: return None

def append_perf(row):
    PERF_DIR.mkdir(parents=True,exist_ok=True)
    with PERF_LOG.open("a",encoding="utf-8") as f:
        f.write(json.dumps(row,ensure_ascii=False,separators=(",",":"))+"\n")

def safe_slug(text,limit=42):
    s=re.sub(r"[^\w\-]+","_",str(text).strip(),flags=re.UNICODE).strip("_")
    return (s[:limit] or "image")

def save_b64(encoded,directory,prefix,label="image"):
    directory.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    name=f"{stamp}_{prefix}_{safe_slug(label)}.png"
    path=directory/name
    path.write_bytes(base64.b64decode(encoded))
    rel=path.relative_to(ROOT)
    return path,"/"+str(rel)

def save_output(encoded,mode,prompt):
    return save_b64(encoded,OUT_DIR,mode,prompt)

def qwen_health():
    try:
        with urllib.request.urlopen(QWEN_BASE+"/health",timeout=2) as r:
            return json.loads(r.read()).get("status")=="ok"
    except Exception: return False

def qwen_models():
    try:
        with urllib.request.urlopen(QWEN_BASE+"/v1/models",timeout=3) as r:
            return [x.get("id") for x in json.loads(r.read()).get("data",[])]
    except Exception: return []

def asset_items():
    items=[]
    for directory,kind in ((OUT_DIR,"generated"),(LIB_DIR,"loaded"),(INTERMEDIATE_DIR,"intermediate")):
        if not directory.exists(): continue
        for p in directory.iterdir():
            if not p.is_file() or p.suffix.lower() not in IMAGE_EXTS: continue
            st=p.stat()
            rel="/"+str(p.relative_to(ROOT))
            inferred=kind
            if kind=="generated" and "_editor_" in p.name: inferred="edited"
            if kind=="generated" and "_mask-final_" in p.name: inferred="edited"
            items.append({
                "name":p.name,"url":rel,"kind":inferred,
                "mtime":st.st_mtime,"bytes":st.st_size,
            })
    items.sort(key=lambda x:x["mtime"],reverse=True)
    return items

def resolve_deletable(url):
    name=Path(str(url)).name
    if not name or name in {".",".."}: raise ValueError("无效文件")
    for root in (OUT_DIR,LIB_DIR,INTERMEDIATE_DIR):
        target=(root/name).resolve()
        if target.parent==root.resolve() and target.is_file():
            return target
    raise ValueError("只允许删除 Workbench 图片库中的文件")

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw):
        super().__init__(*a,directory=str(ROOT),**kw)

    def _json(self,code,obj):
        b=json.dumps(obj,ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Cache-Control","no-store")
        self.send_header("Content-Length",str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def _body(self):
        n=int(self.headers.get("Content-Length","0"))
        return json.loads(self.rfile.read(n))

    def do_GET(self):
        if self.path.startswith("/api/status"):
            return self._json(200,{
                "qwen_ok":qwen_health(),"models":qwen_models(),
                "rss_mb":proc_rss_mb(),"swap_mb":swap_used_mb(),
                "memory_free_pct":memory_free_pct(),"time":now_iso()
            })
        if self.path.startswith("/api/assets"):
            return self._json(200,{"items":asset_items()})
        if self.path.startswith("/api/history"):
            items=[]
            try:
                for line in PERF_LOG.read_text(encoding="utf-8").splitlines()[-120:]:
                    row=json.loads(line)
                    if row.get("success") and row.get("output_url") and not row.get("history_hidden"):
                        p=ROOT/row["output_url"].lstrip("/")
                        if p.is_file(): items.append(row)
            except FileNotFoundError: pass
            return self._json(200,{"items":items[-12:][::-1]})
        if self.path.startswith("/api/performance/latest"):
            try:
                lines=PERF_LOG.read_text(encoding="utf-8").splitlines()
                return self._json(200,json.loads(lines[-1]) if lines else {})
            except FileNotFoundError:
                return self._json(200,{})
        return super().do_GET()

    def do_POST(self):
        if self.path in {"/api/upload-asset","/api/save-editor"}:
            try:
                req=self._body()
                encoded=req["image_b64"]
                label=req.get("name","image")
                if self.path=="/api/upload-asset":
                    path,url=save_b64(encoded,LIB_DIR,"loaded",label)
                    kind="loaded"
                else:
                    path,url=save_b64(encoded,OUT_DIR,"editor",label)
                    kind="edited"
                    append_perf({
                        "started_at":now_iso(),"success":True,"mode":"editor",
                        "source_url":req.get("source_url"),"output_url":url,
                        "output_path":str(path),"output_bytes":decoded_size(encoded),
                        "history_hidden":False,
                    })
                return self._json(200,{"url":url,"name":path.name,"kind":kind})
            except Exception as e:
                return self._json(500,{"error":str(e)})

        if self.path in {"/api/delete-output","/api/delete-asset"}:
            try:
                req=self._body()
                target=resolve_deletable(req.get("output_url") or req.get("url"))
                target.unlink()
                append_perf({"started_at":now_iso(),"success":True,"mode":"delete","deleted":target.name,"history_hidden":True})
                return self._json(200,{"deleted":True,"name":target.name})
            except Exception as e:
                return self._json(500,{"error":str(e)})

        if self.path=="/api/save-composite":
            try:
                req=self._body(); encoded=req["image_b64"]; prompt=req.get("prompt","local-mask")
                path,url=save_output(encoded,"mask-final",prompt)
                row={"started_at":now_iso(),"success":True,"mode":"mask-final","size":req.get("size"),
                     "prompt_chars":len(prompt),"prompt_preview":prompt[:90],"output_bytes":decoded_size(encoded),
                     "output_path":str(path),"output_url":url,"source_size":req.get("source_size"),
                     "mask_percent":req.get("mask_percent"),"qwen_sec":req.get("qwen_sec")}
                append_perf(row)
                return self._json(200,{"output_url":url})
            except Exception as e:
                return self._json(500,{"error":str(e)})

        mode={"/api/generate":"generate","/api/variation":"variation","/api/edit":"edit","/api/mask-edit":"mask-edit"}.get(self.path)
        if not mode: return self._json(404,{"error":"not found"})
        started=time.perf_counter()
        row={"started_at":now_iso(),"success":False,"mode":mode}
        try:
            req=self._body(); prompt=req["prompt"].strip()
            if not prompt: raise ValueError("提示词不能为空")
            size=req.get("size","1024x1024")
            m=re.fullmatch(r"(\d+)x(\d+)",size)
            if not m: raise ValueError("尺寸格式必须是 WIDTHxHEIGHT")
            w,h=map(int,m.groups()); steps=int(req.get("steps",20)); seed=int(req.get("seed",42))
            model=req.get("model","qwen-image-2.1-mlx-8bit")
            payload={"model":model,"prompt":prompt,"size":size,"steps":steps,"seed":seed}
            ref_count=0
            if mode=="variation":
                payload.update({"mode":"variation","image":req["image_b64"],"strength":float(req.get("strength",0.45))}); ref_count=1
            elif mode=="edit":
                refs=req.get("ref_images_b64",[])
                if len(refs)>3: raise ValueError("当前 MLX 后端最多 3 张额外参考图")
                payload.update({"mode":"edit","image":req["image_b64"]}); ref_count=1+len(refs)
                if refs: payload["ref_images"]=refs
            elif mode=="mask-edit":
                payload.update({"mode":"edit","image":req["image_b64"],"ref_images":[req["mask_b64"]]}); ref_count=2
            row.update({
                "model":model,"size":size,"width":w,"height":h,"steps":steps,"seed":seed,
                "history_hidden":mode=="mask-edit","condition_images":ref_count,
                "visual_tokens_est":round((w/32)*(h/32)*ref_count) if ref_count else 0,
                "prompt_chars":len(prompt),"prompt_preview":prompt[:90],
                "source_size":req.get("source_size"),"full_source_size":req.get("full_source_size"),
                "mask_percent":req.get("mask_percent"),"local_strategy":req.get("local_strategy"),
                "mask_bbox":req.get("mask_bbox"),"crop_rect":req.get("crop_rect"),
                "crop_percent":req.get("crop_percent"),
                "strength":req.get("strength"),"rss_before_mb":proc_rss_mb(),
                "swap_before_mb":swap_used_mb(),"memory_free_before_pct":memory_free_pct(),
            })
            q=urllib.request.Request(QWEN_API,data=json.dumps(payload).encode(),headers={"Content-Type":"application/json"},method="POST")
            q0=time.perf_counter()
            with urllib.request.urlopen(q,timeout=7200) as r: out=json.loads(r.read())
            qwen_sec=time.perf_counter()-q0
            encoded=out["data"][0]["b64_json"]
            # mask-edit is only an intermediate AI frame. It must never appear in the image library.
            # The browser applies the frozen mask deterministically, verifies outside-mask pixels,
            # then saves only that final composite through /api/save-editor.
            if mode=="mask-edit":
                path=None; url=None
            else:
                path,url=save_output(encoded,mode,prompt)
            row.update({
                "success":True,"qwen_sec":round(qwen_sec,3),"backend_total_sec":round(time.perf_counter()-started,3),
                "output_bytes":decoded_size(encoded),"output_path":str(path) if path else None,"output_url":url,
                "rss_after_mb":proc_rss_mb(),"swap_after_mb":swap_used_mb(),
                "memory_free_after_pct":memory_free_pct(),
            })
            append_perf(row)
            return self._json(200,{"b64_json":encoded,"output_url":url,"perf":row})
        except urllib.error.HTTPError as e:
            row["error"]=e.read().decode(errors="replace")[:2000]
        except Exception as e:
            row["error"]=str(e)
        row["backend_total_sec"]=round(time.perf_counter()-started,3); append_perf(row)
        return self._json(500,{"error":row.get("error","unknown error"),"perf":row})

if __name__=="__main__":
    OUT_DIR.mkdir(parents=True,exist_ok=True); LIB_DIR.mkdir(parents=True,exist_ok=True); INTERMEDIATE_DIR.mkdir(parents=True,exist_ok=True)
    print(f"Image MLX Lab: http://127.0.0.1:{PORT}/web/mask-editor/")
    ThreadingHTTPServer(("127.0.0.1",PORT),Handler).serve_forever()
