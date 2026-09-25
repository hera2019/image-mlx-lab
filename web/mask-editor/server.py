#!/usr/bin/env python3
import argparse, base64, hashlib, json, os, re, signal, subprocess, threading, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = ROOT / "web" / "mask-editor"
HOST = "127.0.0.1"
PORT = 18080
# Requests must name one of these hosts (DNS-rebinding guard) and, for writes, come from one of
# these origins (cross-site request guard). LAN access is intentionally not supported yet; adding
# it later means extending these sets behind an explicit opt-in.
ALLOWED_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
ALLOWED_ORIGINS = {"http://" + h for h in ALLOWED_HOSTS}
MAX_BODY_BYTES = 256 * 1024 * 1024
# Fingerprint of the code this process is running. The launcher compares it with server.py on
# disk and restarts a stale server after an update (the page itself is always read fresh).
SERVER_VERSION = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:12]

QWEN_PORT = 11234
QWEN_BASE = f"http://127.0.0.1:{QWEN_PORT}"
QWEN_API = QWEN_BASE + "/v1/images/generations"
PERF_DIR = ROOT / "results" / "performance"
PERF_LOG = PERF_DIR / "qwen-workbench.jsonl"
OUT_DIR = ROOT / "results" / "web"
LIB_DIR = ROOT / "results" / "library"
INTERMEDIATE_DIR = ROOT / "results" / "intermediate"
LIBRARY_DIRS = (OUT_DIR, LIB_DIR, INTERMEDIATE_DIR)
IMAGE_EXTS = {".png",".jpg",".jpeg",".webp"}
WEB_STATIC_EXTS = {".html",".js",".css",".svg",".ico"}

SETTINGS_PATH = ROOT / "results" / "settings.json"
MODEL_ROOT = Path.home() / "Documents" / "AI-Models" / "image"
MODEL_LOG = Path.home() / ".mlx-serve" / "logs" / "image-mlx-lab-model.log"
START_SCRIPT = ROOT / "scripts" / "start_server.sh"
VARIANTS = {
    "4bit": {"id":"qwen-image-2.1-mlx-4bit","label":"4-bit","size_gb":10.0,
             "note":"约 10 GB。占用内存少，推荐 32 GB 及以下内存的 Mac。"},
    "8bit": {"id":"qwen-image-2.1-mlx-8bit","label":"8-bit","size_gb":17.6,
             "note":"约 17.6 GB。量化损失更小；推荐 48 GB 以上内存，32 GB 机器通常需要跳过内存预检。"},
}
RECOMMEND_8BIT_RAM_GB = 48
EDIT_VISION_FILE = "text_encoder/qwen21_visual.safetensors"   # needed by True Edit / AI local edit

def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")

def listener_pids(port):
    try:
        out=subprocess.check_output(["lsof","-nP","-t",f"-iTCP:{port}","-sTCP:LISTEN"],text=True,stderr=subprocess.DEVNULL)
        return [int(x) for x in out.split()]
    except Exception: return []

def proc_command(pid):
    try: return subprocess.check_output(["ps","-o","command=","-p",str(pid)],text=True).strip()
    except Exception: return ""

def proc_rss_mb():
    try:
        pids=listener_pids(QWEN_PORT)
        if not pids: return None
        rss=subprocess.check_output(["ps","-o","rss=","-p",str(pids[0])],text=True).strip()
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

def total_ram_gb():
    try: return round(int(subprocess.check_output(["sysctl","-n","hw.memsize"],text=True))/1024**3)
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

def qwen_model_rows():
    try:
        with urllib.request.urlopen(QWEN_BASE+"/v1/models",timeout=3) as r:
            return json.loads(r.read()).get("data",[])
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

def resolve_managed_file(url):
    raw=str(url or "").split("?",1)[0]
    if not raw: raise ValueError("无效文件")
    target=(ROOT/raw.lstrip("/")).resolve()
    for root in LIBRARY_DIRS:
        if target.parent==root.resolve() and target.is_file():
            return target
    raise ValueError("只允许操作 Workbench 图片库中的文件")

def static_target(url_path):
    """Map a GET path to a file the UI may load, or None. Nothing else in the repo is served."""
    path=urllib.parse.unquote(urllib.parse.urlsplit(url_path).path)
    if path in {"/web/mask-editor","/web/mask-editor/"}: return WEB_DIR/"index.html"
    target=(ROOT/path.lstrip("/")).resolve()
    if path.startswith("/web/mask-editor/"):
        try: rel=target.relative_to(WEB_DIR)
        except ValueError: return None
        if any(p.startswith(".") or p in {"backups","__pycache__"} for p in rel.parts): return None
        return target if target.is_file() and target.suffix.lower() in WEB_STATIC_EXTS else None
    if path.startswith("/results/"):
        for d in LIBRARY_DIRS:
            if target.parent==d.resolve() and target.is_file() and target.suffix.lower() in IMAGE_EXTS: return target
    return None

def load_settings():
    try: return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception: return {}

def save_settings(data):
    SETTINGS_PATH.parent.mkdir(parents=True,exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

class ModelManager:
    """Owns the local mlx-serve process: which quantized variant runs, starting, and switching."""

    def __init__(self):
        self.proc=None
        self.log_offset=0
        self.switching=False
        self.error=None
        self.ram_gb=total_ram_gb()

    def installed(self):
        return [k for k,v in VARIANTS.items() if (MODEL_ROOT/v["id"]/"model_index.json").is_file()]

    def edit_ready(self,variant):
        return variant in VARIANTS and (MODEL_ROOT/VARIANTS[variant]["id"]/EDIT_VISION_FILE).is_file()

    def edit_missing_message(self,variant):
        v=VARIANTS[variant]
        return (f"{v['label']} 缺少编辑用视觉模块，指令编辑和 AI 局部编辑暂时不可用（文生图、图生图不受影响）。"
                f"补齐方法（约 1.1 GB）：.venv/bin/python scripts/fetch_edit_vision.py --model-dir ~/Documents/AI-Models/image/{v['id']}")

    def recommended(self):
        inst=self.installed()
        if "8bit" in inst and (self.ram_gb or 0)>=RECOMMEND_8BIT_RAM_GB: return "8bit"
        if "4bit" in inst: return "4bit"
        return inst[0] if inst else "4bit"

    def desired(self):
        s=load_settings()
        variant=s.get("model_variant")
        if variant not in self.installed(): variant=self.recommended()
        return variant,bool(s.get("skip_mem_preflight",False))

    def running(self):
        """The mlx-serve process currently listening on the model port, if any."""
        for pid in listener_pids(QWEN_PORT):
            cmd=proc_command(pid)
            if "mlx-serve" not in cmd: continue
            variant=next((k for k,v in VARIANTS.items() if "/"+v["id"] in cmd),None)
            return {"pid":pid,"variant":variant,"skip_mem_preflight":"--skip-mem-preflight" in cmd}
        return None

    def failure_detail(self,variant=None):
        """(summary, log excerpt) for the last start attempt, preferring the lines that explain the failure."""
        try:
            with MODEL_LOG.open("rb") as f:
                f.seek(self.log_offset); text=f.read().decode("utf-8","replace")
        except Exception: return None,""
        lines=text.strip().splitlines()
        key=[l for l in lines if re.search(r"(?i)insufficient|error|fail|preflight|not found|用法|不存在|未构建",l)]
        excerpt="\n".join((key or lines)[-6:])
        m=re.search(r"needs ~([\d.]+) GB free.*?only ([\d.]+) GB is available",text)
        if m:
            return (f"可用内存不足：加载需要约 {m.group(1)} GB 空闲内存，当前只有 {m.group(2)} GB。"
                    "可以关闭其他占内存的应用后重试"+("" if variant=="4bit" else "、改用 4-bit")+"，或勾选“跳过内存预检”（可能大量使用 swap）。"),excerpt
        return None,excerpt

    def phase(self,running=None,rows=None):
        if self.switching: return "switching"
        running=running if running is not None else self.running()
        if running:
            rows=rows if rows is not None else (qwen_model_rows() if qwen_health() else [])
            if rows and all(r.get("state","ready")=="ready" for r in rows): return "ready"
            return "loading"
        if not self.installed(): return "missing"
        if self.proc and self.proc.poll() is None: return "loading"
        if self.proc or self.error: return "failed"
        return "stopped"

    def status(self):
        running=self.running()
        rows=qwen_model_rows() if running and qwen_health() else []
        phase=self.phase(running,rows)
        variant,skip=self.desired()
        out={
            "phase":phase,"ram_gb":self.ram_gb,"installed":self.installed(),"recommended":self.recommended(),
            "desired_variant":variant,"desired_skip_mem_preflight":skip,
            "active_variant":running and running["variant"],
            "active_skip_mem_preflight":bool(running and running["skip_mem_preflight"]),
            "active_model_id":rows[0].get("id") if rows else None,
            "variants":{k:{"id":v["id"],"label":v["label"],"size_gb":v["size_gb"],"note":v["note"],
                           "edit_ready":self.edit_ready(k)} for k,v in VARIANTS.items()},
        }
        if phase=="failed":
            summary,excerpt=self.failure_detail(variant)
            out["error"]=self.error or summary or "模型进程已退出"
            out["log_tail"]=excerpt
        return out

    def model_id(self):
        rows=qwen_model_rows()
        if rows and rows[0].get("id"): return rows[0]["id"]
        return VARIANTS[self.desired()[0]]["id"]

    def start(self,variant,skip):
        MODEL_LOG.parent.mkdir(parents=True,exist_ok=True)
        with MODEL_LOG.open("ab") as log:
            self.log_offset=log.tell()
            log.write(f"\n=== {now_iso()} Image MLX Lab: start {variant} ({'skip' if skip else 'with'} memory preflight) ===\n".encode())
            log.flush()
            self.error=None
            self.proc=subprocess.Popen(
                [str(START_SCRIPT),variant,"force" if skip else "safe"],
                cwd=str(ROOT),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,
            )

    def stop(self,timeout=30):
        pids={p for p in listener_pids(QWEN_PORT) if "mlx-serve" in proc_command(p)}
        if self.proc and self.proc.poll() is None: pids.add(self.proc.pid)
        for pid in pids:
            try: os.kill(pid,signal.SIGTERM)
            except ProcessLookupError: pass
        deadline=time.time()+timeout
        while time.time()<deadline and any(self._alive(p) for p in pids): time.sleep(0.3)
        for pid in pids:
            if self._alive(pid):
                try: os.kill(pid,signal.SIGKILL)
                except ProcessLookupError: pass
        if self.proc: self.proc.poll()

    def _alive(self,pid):
        if self.proc and self.proc.pid==pid: return self.proc.poll() is None
        try: os.kill(pid,0); return True
        except OSError: return False

    def ensure_started(self):
        if self.running(): return
        variant,skip=self.desired()
        if variant not in self.installed():
            self.error=None
            return
        self.start(variant,skip)

    def switch(self,variant,skip,release):
        """Runs in a background thread; `release` frees the job lock once the new process is launched."""
        try:
            self.stop(); self.start(variant,skip)
        except Exception as e:
            self.error=f"切换模型失败：{e}"
        finally:
            self.switching=False; release()

MODELS=ModelManager()
JOB_LOCK=threading.Lock()   # one model job (generation / AI edit / model switch) at a time
CURRENT_JOB={}

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw):
        super().__init__(*a,directory=str(ROOT),**kw)

    def log_message(self,fmt,*args):
        if "/api/status" not in getattr(self,"path",""): super().log_message(fmt,*args)

    def translate_path(self,path):
        target=static_target(path)
        return str(target) if target else str(ROOT/".not-served")

    def send_head(self):
        self._static=True
        return super().send_head()

    def end_headers(self):
        # Static files revalidate on every load (304 when unchanged) so a refreshed page never pairs
        # a heuristically cached index.html with a newer app.js.
        if getattr(self,"_static",False): self.send_header("Cache-Control","no-cache")
        super().end_headers()

    def _json(self,code,obj):
        b=json.dumps(obj,ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Cache-Control","no-store")
        self.send_header("Content-Length",str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def _host_ok(self):
        if (self.headers.get("Host") or "").lower() in ALLOWED_HOSTS: return True
        self.send_error(403,"Host not allowed"); return False

    def _write_ok(self):
        origin=self.headers.get("Origin")
        site=self.headers.get("Sec-Fetch-Site")
        ctype=(self.headers.get("Content-Type") or "").split(";",1)[0].strip().lower()
        if (origin and origin not in ALLOWED_ORIGINS) or site not in (None,"same-origin","none"):
            self._json(403,{"error":"只接受来自本机 Workbench 页面的请求"}); return False
        if ctype!="application/json":
            self._json(415,{"error":"请求必须是 application/json"}); return False
        return True

    def _body(self):
        n=int(self.headers.get("Content-Length","0"))
        if n>MAX_BODY_BYTES: raise ValueError("请求体过大")
        return json.loads(self.rfile.read(n))

    def do_HEAD(self):
        if self._host_ok(): super().do_HEAD()

    def do_GET(self):
        if not self._host_ok(): return
        path=urllib.parse.urlsplit(self.path).path
        if path=="/":
            self.send_response(302); self.send_header("Location","/web/mask-editor/"); self.end_headers(); return
        if path=="/api/status":
            m=MODELS.status()
            return self._json(200,{
                "server_version":SERVER_VERSION,
                "qwen_ok":m["phase"]=="ready","model":m,"busy":dict(CURRENT_JOB) or None,
                "rss_mb":proc_rss_mb(),"swap_mb":swap_used_mb(),
                "memory_free_pct":memory_free_pct(),"time":now_iso()
            })
        if path=="/api/assets":
            return self._json(200,{"items":asset_items()})
        if path=="/api/performance/latest":
            try:
                lines=PERF_LOG.read_text(encoding="utf-8").splitlines()
                return self._json(200,json.loads(lines[-1]) if lines else {})
            except FileNotFoundError:
                return self._json(200,{})
        return super().do_GET()

    def do_POST(self):
        if not self._host_ok() or not self._write_ok(): return
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
                        "edit_kind":req.get("edit_kind"),
                        "ai_context_mode":req.get("ai_context_mode"),
                        "ai_framing_mode":req.get("ai_framing_mode"),
                        "ai_framing_local_score":req.get("ai_framing_local_score"),
                        "ai_framing_full_score":req.get("ai_framing_full_score"),
                        "mask_bbox":req.get("mask_bbox"),"crop_rect":req.get("crop_rect"),
                        "mask_percent":req.get("mask_percent"),
                    })
                return self._json(200,{"url":url,"name":path.name,"kind":kind})
            except Exception as e:
                return self._json(500,{"error":str(e)})

        if self.path=="/api/overwrite-editor":
            try:
                req=self._body()
                encoded=req["image_b64"]
                source_url=req.get("source_url")
                target=resolve_managed_file(source_url)
                target.write_bytes(base64.b64decode(encoded))
                append_perf({
                    "started_at":now_iso(),"success":True,"mode":"editor-overwrite",
                    "source_url":source_url,"output_url":source_url,
                    "output_path":str(target),"output_bytes":decoded_size(encoded),
                    "history_hidden":False,
                })
                return self._json(200,{"url":source_url,"name":target.name,"kind":"edited"})
            except Exception as e:
                return self._json(500,{"error":str(e)})

        if self.path=="/api/delete-asset":
            try:
                req=self._body()
                target=resolve_managed_file(req.get("url"))
                target.unlink()
                append_perf({"started_at":now_iso(),"success":True,"mode":"delete","deleted":target.name,"history_hidden":True})
                return self._json(200,{"deleted":True,"name":target.name})
            except Exception as e:
                return self._json(500,{"error":str(e)})

        if self.path=="/api/model":
            try:
                req=self._body()
                variant=req.get("variant"); skip=bool(req.get("skip_mem_preflight",False))
                if variant not in VARIANTS: raise ValueError("未知模型版本")
                if variant not in MODELS.installed():
                    raise ValueError(f"{VARIANTS[variant]['label']} 尚未下载，请先运行 scripts/setup_model.py --model {VARIANTS[variant]['id']}")
            except Exception as e:
                return self._json(400,{"error":str(e)})
            running=MODELS.running()
            phase=MODELS.phase(running)
            if phase in {"switching","loading"}:
                return self._json(409,{"error":"模型正在加载，请等它就绪后再切换。"})
            if running and running["variant"]==variant and running["skip_mem_preflight"]==skip:
                save_settings({**load_settings(),"model_variant":variant,"skip_mem_preflight":skip})
                return self._json(200,{"switching":False,"model":MODELS.status()})
            if not JOB_LOCK.acquire(blocking=False):
                return self._json(409,{"error":"有生成 / AI 编辑任务正在运行，完成后再切换模型。"})
            save_settings({**load_settings(),"model_variant":variant,"skip_mem_preflight":skip})
            MODELS.switching=True
            threading.Thread(target=MODELS.switch,args=(variant,skip,JOB_LOCK.release),daemon=True).start()
            return self._json(202,{"switching":True})

        mode={"/api/generate":"generate","/api/variation":"variation","/api/edit":"edit","/api/mask-edit":"mask-edit"}.get(self.path)
        if not mode: return self._json(404,{"error":"not found"})
        phase=MODELS.phase()
        if phase!="ready":
            msg={"loading":"模型正在加载，请稍候再试。","switching":"正在切换模型，请稍候再试。"}.get(phase,"模型没有运行。请在右上角模型设置中检查状态。")
            return self._json(503,{"error":msg})
        if mode in {"edit","mask-edit"}:
            active=(MODELS.running() or {}).get("variant")
            if active and not MODELS.edit_ready(active):
                return self._json(400,{"error":MODELS.edit_missing_message(active)})
        if not JOB_LOCK.acquire(blocking=False):
            return self._json(409,{"error":"另一个生成 / AI 编辑任务正在运行，请等它完成后再试。","busy":dict(CURRENT_JOB)})
        try:
            CURRENT_JOB.update({"mode":mode,"started_at":now_iso()})
            return self._run_model_job(mode)
        finally:
            CURRENT_JOB.clear(); JOB_LOCK.release()

    def _run_model_job(self,mode):
        started=time.perf_counter()
        row={"started_at":now_iso(),"success":False,"mode":mode}
        try:
            req=self._body(); prompt=req["prompt"].strip()
            if not prompt: raise ValueError("提示词不能为空")
            size=req.get("size","1024x1024")
            m=re.fullmatch(r"(\d+)x(\d+)",size)
            if not m: raise ValueError("尺寸格式必须是 WIDTHxHEIGHT")
            w,h=map(int,m.groups()); steps=int(req.get("steps",20)); seed=int(req.get("seed",42))
            model=MODELS.model_id()
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
                refs=[req["mask_b64"]]
                context_b64=req.get("context_b64")
                if context_b64:
                    refs.append(context_b64)
                if len(refs)>3:
                    raise ValueError("Mask 编辑参考图数量超出当前 MLX 上限")
                payload.update({"mode":"edit","image":req["image_b64"],"ref_images":refs})
                ref_count=1+len(refs)
            row.update({
                "model":model,"size":size,"width":w,"height":h,"steps":steps,"seed":seed,
                "history_hidden":mode=="mask-edit","condition_images":ref_count,
                "visual_tokens_est":round((w/32)*(h/32)*ref_count) if ref_count else 0,
                "prompt_chars":len(prompt),"prompt_preview":prompt[:90],
                "source_size":req.get("source_size"),"full_source_size":req.get("full_source_size"),
                "mask_percent":req.get("mask_percent"),"local_strategy":req.get("local_strategy"),
                "requested_context_mode":req.get("requested_context_mode"),
                "resolved_context_mode":req.get("resolved_context_mode"),
                "context_size":req.get("context_size"),
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
    ap=argparse.ArgumentParser(description="Image MLX Lab web UI (localhost only)")
    ap.add_argument("--no-model",action="store_true",help="不自动启动本地模型服务（只调试界面时使用）")
    args=ap.parse_args()
    for d in LIBRARY_DIRS: d.mkdir(parents=True,exist_ok=True)
    if not args.no_model:
        MODELS.ensure_started()
    print(f"Image MLX Lab: http://{HOST}:{PORT}/web/mask-editor/",flush=True)
    ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
