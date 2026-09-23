const SAMPLE="/results/generated/This_is_an_RGBA_image_wi_20260922-145953-981170.png";
const $=id=>document.getElementById(id);
const tabs=[...document.querySelectorAll(".tabs button")];
const panels={generate:$("panel-generate"),variation:$("panel-variation"),edit:$("panel-edit")};
const genControls=$("genControls"),editorTools=$("editorTools");
const qwenBadge=$("qwenBadge"),memBadge=$("memBadge"),statusText=$("statusText"),perfBox=$("perfBox");
const sizePreset=$("sizePreset"),widthInput=$("widthInput"),heightInput=$("heightInput"),stepsInput=$("stepsInput"),seedInput=$("seedInput"),tokenHint=$("tokenHint");

let mode="generate",variationAsset=null,editAsset=null,editRefQueue=[],lastGen=null,assets=[];
let editorSource=null,currentViewScale=1,selectionTool="rect",drawing=false,lastPoint=null,shapeStart=null,shapeBase=null;
let workHistory=[],workHistoryIndex=-1,clipboard=null,floating=null,dragStart=null,adjustTimer=null;

const workCanvas=document.createElement("canvas"),workCtx=workCanvas.getContext("2d",{willReadFrequently:true});
const selectionCanvas=document.createElement("canvas"),selCtx=selectionCanvas.getContext("2d",{willReadFrequently:true});
const sourceCanvas=$("sourceCanvas"),displayCtx=sourceCanvas.getContext("2d",{willReadFrequently:true});
const overlayCanvas=$("overlayCanvas"),overlayCtx=overlayCanvas.getContext("2d",{willReadFrequently:true});
const editorStage=$("editorStage"),editorViewport=$("editorViewport");

function dataUrlToB64(url){return url.split(",")[1]}
function imgFromUrl(url){return new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>resolve(im);im.onerror=reject;im.src=url})}
function assetFromDataUrl(name,dataUrl){return imgFromUrl(dataUrl).then(img=>({name,dataUrl,b64:dataUrlToB64(dataUrl),w:img.naturalWidth,h:img.naturalHeight,img}))}
function blobToAsset(blob,name){return new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>assetFromDataUrl(name,r.result).then(resolve,reject);r.onerror=reject;r.readAsDataURL(blob)})}
async function fileAsset(file){return blobToAsset(file,file.name)}
async function remoteAsset(url,name="image.png"){const r=await fetch(url,{cache:"no-store"});if(!r.ok)throw new Error("图片读取失败");return blobToAsset(await r.blob(),name)}
function round32(v){return Math.max(256,Math.min(2048,Math.round(v/32)*32))}
function roleLabel(v){return({identity:"身份/五官",pose:"姿态",clothes:"服装/配饰",style:"风格",detail:"细节",other:"其他"})[v]||"参考"}
let genPerfText="";
let noticeLog=[];
let noticeSelected=0;
function renderNoticeHistory(){
  const box=$("noticeHistory");if(!box)return;box.innerHTML="";
  noticeLog.forEach((item,i)=>{
    const row=document.createElement("div");row.className="noticeHistoryItem"+(i===noticeSelected?" active":"");
    const first=item.message.split("\n")[0]||"状态";
    row.innerHTML="<b>"+escapeHtml(item.time)+" · "+escapeHtml(item.scope)+"</b>"+escapeHtml(first);
    row.onclick=()=>{noticeSelected=i;$("noticeDetail").textContent=item.message;renderNoticeHistory()};
    box.appendChild(row);
  });
  box.scrollTop=0;
}
function notify(message,scope=null,open=true){
  const kind=scope==="editor"?"编辑":scope==="gen"?"生成":(mode==="editor"?"编辑":"生成");
  const time=new Date().toLocaleTimeString("zh-CN",{hour12:false});
  noticeLog.unshift({time,scope:kind,message:String(message)});
  if(noticeLog.length>80)noticeLog.length=80;
  noticeSelected=0;
  if($("noticeDetail"))$("noticeDetail").textContent=String(message);
  if($("noticeSummary"))$("noticeSummary").textContent=(String(message).split("\n")[0]||"状态");
  renderNoticeHistory();
  const drawer=$("globalNoticeDrawer");if(drawer&&open)drawer.open=true;
}
function formatPerf(p){
  if(!p)return "";
  const mb=v=>v==null?"—":Number(v).toFixed(0)+" MB";
  return "Qwen "+(p.qwen_sec??"—")+" s · 后端 "+(p.backend_total_sec??"—")+" s · "+(p.size??"—")+" · Steps "+(p.steps??"—")+" · Seed "+(p.seed??"—")+" · Swap "+mb(p.swap_before_mb)+" → "+mb(p.swap_after_mb);
}
function cloneCanvas(src){
  const c=document.createElement("canvas");c.width=src.width;c.height=src.height;c.getContext("2d").drawImage(src,0,0);return c;
}

function currentMainAsset(){
  if(!workCanvas.width)return null;
  const dataUrl=workCanvas.toDataURL("image/png");
  return {
    ...(editorSource||{}),
    name:editorSource?.name||"current-main.png",
    dataUrl,
    b64:dataUrlToB64(dataUrl),
    w:workCanvas.width,
    h:workCanvas.height,
  };
}
function syncCurrentMainToMode(){
  const current=currentMainAsset();if(!current)return;
  if(mode==="variation"){
    variationAsset=current;
    $("variationInfo").textContent=current.name+" · "+current.w+"×"+current.h;
  }else if(mode==="edit"){
    editAsset=current;
    $("editInfo").textContent=current.name+" · "+current.w+"×"+current.h;
  }
}
function setMode(next){
  mode=next;
  tabs.forEach(b=>b.classList.toggle("active",b.dataset.mode===mode));
  const editing=mode==="editor";
  genControls.classList.toggle("hidden",editing);
  editorTools.classList.toggle("hidden",!editing);
  Object.entries(panels).forEach(([k,p])=>p.classList.toggle("hidden",editing||k!==mode));
  if(!editing){
    syncCurrentMainToMode();
    if(sizePreset.value==="auto")autoGenSize();else updateTokenHint();
  }
  renderEditor();
}
tabs.forEach(b=>b.onclick=()=>setMode(b.dataset.mode));

/* ---------- 前三项：生成 ---------- */
function activeRefs(){return editRefQueue.filter(x=>x.active).slice(0,3)}
function genAsset(){return mode==="variation"?variationAsset:mode==="edit"?editAsset:null}
function genRefCount(){return mode==="generate"?0:mode==="variation"?(variationAsset?1:0):mode==="edit"?(editAsset?1+activeRefs().length:0):0}
function autoGenSize(){
  const a=genAsset(),refs=genRefCount();let w=a?.w||1024,h=a?.h||1024,s=1;
  if(refs){const t=(w/32)*(h/32)*refs;if(t>1450)s=Math.min(s,Math.sqrt(1450/t));if(Math.max(w*s,h*s)>1152)s*=1152/Math.max(w*s,h*s)}
  else if(Math.max(w,h)>1024)s=1024/Math.max(w,h);
  widthInput.value=round32(w*s);heightInput.value=round32(h*s);updateTokenHint();
}
function updateTokenHint(){
  const w=+widthInput.value||1024,h=+heightInput.value||1024,r=genRefCount();
  if(!r){tokenHint.className="hint safe";tokenHint.textContent="文生图：无参考图视觉 token 限制";return}
  const t=Math.round((w/32)*(h/32)*r);tokenHint.textContent="视觉 token 估算："+t+" · 条件图 "+r+" 张";
  tokenHint.className="hint "+(t<=1450?"safe":t<=1850?"warn":"danger");
}
sizePreset.onchange=()=>{if(sizePreset.value==="auto")autoGenSize();else if(sizePreset.value!=="custom"){const [w,h]=sizePreset.value.split("x");widthInput.value=w;heightInput.value=h;updateTokenHint()}};
widthInput.onchange=()=>{sizePreset.value="custom";widthInput.value=round32(+widthInput.value);updateTokenHint()};
heightInput.onchange=()=>{sizePreset.value="custom";heightInput.value=round32(+heightInput.value);updateTokenHint()};
$("autoFit").onclick=()=>{sizePreset.value="auto";autoGenSize()};
$("randomSeed").onclick=()=>seedInput.value=Math.floor(Math.random()*2147483647);
$("strength").oninput=e=>$("strengthVal").textContent=Number(e.target.value).toFixed(2);
document.querySelectorAll("[data-prompt-target]").forEach(b=>b.onclick=()=>{const el=$(b.dataset.promptTarget);el.value=(el.value.trim()?el.value.trim()+" ":"")+b.dataset.text;el.focus()});

async function persistLoadedAsset(a){
  try{
    const r=await fetch("/api/upload-asset",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({image_b64:a.b64,name:a.name})});
    const j=await r.json();if(r.ok){await refreshAssets();return j}
  }catch(e){}
  return null;
}
async function chooseGenOne(input,which){
  const f=input.files?.[0];if(!f)return;
  try{
    const a=await fileAsset(f),saved=await persistLoadedAsset(a);
    if(which==="variation"){variationAsset=a;$("variationInfo").textContent=a.name+" · "+a.w+"×"+a.h}
    else{editAsset=a;$("editInfo").textContent=a.name+" · "+a.w+"×"+a.h}
    if(saved)await openEditorAsset(saved);
    if(sizePreset.value==="auto")autoGenSize();
  }catch(e){notify("图片读取失败："+e.message,"gen")}
}
$("variationFile").onchange=e=>chooseGenOne(e.target,"variation");
$("editFile").onchange=e=>chooseGenOne(e.target,"edit");
async function loadSample(which){
  try{
    await openEditorAsset({url:SAMPLE,name:"测试透明鱼.png",kind:"generated"});
    if(which==="variation")variationAsset=editorSource;
    else editAsset=editorSource;
    syncCurrentMainToMode();
    if(sizePreset.value==="auto")autoGenSize();
  }catch(e){notify(e.message,"gen")}
}
$("variationSample").onclick=()=>loadSample("variation");$("editSample").onclick=()=>loadSample("edit");
$("editRefs").onchange=async e=>{
  for(const f of [...(e.target.files||[])]){const a=await fileAsset(f);persistLoadedAsset(a);editRefQueue.push({asset:a,active:activeRefs().length<3,role:"other"})}
  e.target.value="";renderRefQueue();if(sizePreset.value==="auto")autoGenSize();updateTokenHint();
};
function renderRefQueue(){
  const box=$("refQueue");box.innerHTML="";
  editRefQueue.forEach((item,i)=>{
    const row=document.createElement("div");row.className="refItem";
    const img=document.createElement("img");img.src=item.asset.dataUrl;
    const main=document.createElement("div"),name=document.createElement("div");name.className="refName";name.textContent=(i+1)+". "+item.asset.name;
    const ctl=document.createElement("div");ctl.className="refControls";
    const lab=document.createElement("label"),ck=document.createElement("input");ck.type="checkbox";ck.checked=item.active;lab.append(ck,document.createTextNode("启用"));
    ck.onchange=()=>{if(ck.checked&&activeRefs().length>=3){ck.checked=false;notify("当前最多启用 3 张额外参考图。","gen");return}item.active=ck.checked;autoGenSize()};
    const sel=document.createElement("select");["identity","pose","clothes","style","detail","other"].forEach(v=>sel.add(new Option(roleLabel(v),v)));sel.value=item.role;sel.onchange=()=>item.role=sel.value;
    ctl.append(lab,sel);main.append(name,ctl);
    const act=document.createElement("div");act.className="refActions";
    for(const [txt,d] of [["↑",-1],["↓",1]]){const b=document.createElement("button");b.textContent=txt;b.onclick=()=>moveRef(i,d);act.append(b)}
    const del=document.createElement("button");del.textContent="×";del.onclick=()=>{editRefQueue.splice(i,1);renderRefQueue();autoGenSize()};act.append(del);
    row.append(img,main,act);box.append(row);
  });
}
function moveRef(i,d){const j=i+d;if(j<0||j>=editRefQueue.length)return;[editRefQueue[i],editRefQueue[j]]=[editRefQueue[j],editRefQueue[i]];renderRefQueue()}

function showPerf(p){
  genPerfText=formatPerf(p);
  if(perfBox)perfBox.textContent=genPerfText;
}
function showGenResult(dataUrl,url){
  lastGen={dataUrl,url};
}
$("runBtn").onclick=async()=>{
  const w=round32(+widthInput.value),h=round32(+heightInput.value),size=w+"x"+h,steps=+stepsInput.value||20,seed=+seedInput.value||42;
  let endpoint,payload;
  if(mode==="generate"){
    let prompt=$("genPrompt").value.trim();if(!prompt){notify("请输入提示词。","gen");return}if($("transparentBg").checked)prompt+=" 这是RGBA透明图片，背景透明，保留Alpha通道。";
    endpoint="/api/generate";payload={prompt,size,steps,seed};
  }else if(mode==="variation"){
    if(!variationAsset){notify("请先选择原图。","gen");return}const prompt=$("variationPrompt").value.trim();if(!prompt){notify("请输入目标描述。","gen");return}
    endpoint="/api/variation";payload={prompt,size,steps,seed,image_b64:variationAsset.b64,strength:+$("strength").value,source_size:variationAsset.w+"x"+variationAsset.h};
  }else{
    if(!editAsset){notify("请先选择主图。","gen");return}let prompt=$("editPrompt").value.trim();if(!prompt){notify("请输入编辑指令。","gen");return}
    const refs=activeRefs();prompt=refs.map((r,i)=>"<image"+(i+2)+">仅作为"+roleLabel(r.role)+"参考。").join("")+prompt;
    endpoint="/api/edit";payload={prompt,size,steps,seed,image_b64:editAsset.b64,ref_images_b64:refs.map(x=>x.asset.b64),source_size:editAsset.w+"x"+editAsset.h};
  }
  notify("生成中… "+size+" · Steps "+steps,"gen");$("runBtn").disabled=true;const oldRunText=$("runBtn").textContent;$("runBtn").textContent="生成中…";
  try{
    const t0=performance.now(),r=await fetch(endpoint,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)}),j=await r.json();
    if(!r.ok)throw new Error(j.error||"生成失败");
    const dataUrl="data:image/png;base64,"+j.b64_json;showGenResult(dataUrl,j.output_url);showPerf(j.perf);
    await Promise.all([loadHistory(),refreshAssets()]);
    await new Promise(r=>setTimeout(r,80));await refreshAssets();
    if(j.output_url)await openEditorByUrl(j.output_url);
    notify("生成完成 · 浏览器总等待 "+((performance.now()-t0)/1000).toFixed(2)+" s\n"+genPerfText+
      "\n新图已显示在中间主窗口，并加入右侧图片库；原图/上一代仍保留在右侧。","gen");
  }catch(e){notify("生成失败："+e.message,"gen")}finally{$("runBtn").disabled=false;$("runBtn").textContent=oldRunText}
};

/* ---------- 图片库 ---------- */
async function refreshAssets(){
  try{const j=await fetch("/api/assets",{cache:"no-store"}).then(r=>r.json());assets=j.items||[];renderAssets()}catch(e){}
}
function renderAssets(){
  const box=$("assetGallery"),filter=$("assetFilter").value;box.innerHTML="";
  const list=assets.filter(a=>filter==="all"||(filter==="final"&&a.kind!=="intermediate")||a.kind===filter);
  if(!list.length){box.innerHTML="<div class='fileInfo'>暂无图片</div>";return}
  list.forEach(a=>{
    const card=document.createElement("div");card.className="assetCard"+(editorSource?.url===a.url?" active":"");
    const img=document.createElement("img");img.src=a.url;img.loading="lazy";
    const meta=document.createElement("div");meta.className="assetMeta";meta.innerHTML="<b>"+escapeHtml(a.name)+"</b>"+kindLabel(a.kind)+" · "+formatBytes(a.bytes);
    const ops=document.createElement("div");ops.className="assetOps";
    const dl=document.createElement("a");dl.href=a.url;dl.download=a.name;dl.textContent="下载";dl.onclick=e=>e.stopPropagation();
    const del=document.createElement("button");del.className="danger";del.textContent="删除";del.onclick=e=>{e.stopPropagation();deleteAsset(a)};
    ops.append(dl,del);card.append(img,meta,ops);card.onclick=()=>openEditorAsset(a);box.append(card);
  });
}
function kindLabel(k){return k==="loaded"?"载入":k==="edited"?"编辑":k==="intermediate"?"中间/原始AI":"生成"}
function formatBytes(n){if(!n)return "—";return n>1048576?(n/1048576).toFixed(1)+"MB":Math.round(n/1024)+"KB"}
function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]))}
$("assetFilter").onchange=renderAssets;$("refreshAssets").onclick=refreshAssets;
async function deleteAsset(a){
  if(!confirm("删除这张图片？\n"+a.name))return;
  const r=await fetch("/api/delete-asset",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url:a.url})}),j=await r.json();
  if(!r.ok){notify(j.error||"删除失败","editor");return}
  if(editorSource?.url===a.url){editorSource={...editorSource,url:null};notify("原图片已删除；当前草稿仍可继续编辑或保存为新图片。","editor")}
  await Promise.all([refreshAssets(),loadHistory()]);
}
async function saveTempAsset(a,name){
  const r=await fetch("/api/upload-asset",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({image_b64:a.b64,name:name||a.name})}),j=await r.json();
  if(!r.ok)return null;await refreshAssets();return assets.find(x=>x.url===j.url)||{url:j.url,name:j.name,kind:j.kind};
}
$("editorUpload").onchange=async e=>{
  const files=[...(e.target.files||[])];if(!files.length)return;
  let first=null;
  for(const f of files){const a=await fileAsset(f);const saved=await saveTempAsset(a,f.name);if(!first)first=saved}
  e.target.value="";if(first)openEditorAsset(first);
};

/* ---------- 编辑器草稿 ---------- */
async function openEditorByUrl(url){const a=assets.find(x=>x.url===url)||{url,name:url.split("/").pop(),kind:"generated"};return openEditorAsset(a)}
async function openEditorAsset(item){
  try{
    const a=await remoteAsset(item.url,item.name);
    editorSource={...item,...a,url:item.url,kind:item.kind||"generated"};
    workCanvas.width=a.w;workCanvas.height=a.h;workCtx.clearRect(0,0,workCanvas.width,workCanvas.height);workCtx.drawImage(a.img,0,0);
    resetSelection();floating=null;clipboardControls();resetAdjust(false);resetWorkHistory();syncEditorSizeInputs();
    syncCurrentMainToMode();
    $("editorTitle").textContent=item.name;
    notify("当前主图："+item.name+"\n顶部模式未改变；右侧可继续切换其他图片比较。",mode==="editor"?"editor":"gen",false);
    renderEditor();renderAssets();
  }catch(e){notify("无法打开图片："+e.message,mode==="editor"?"editor":"gen")}
}
function resetSelection(){
  selectionCanvas.width=workCanvas.width;selectionCanvas.height=workCanvas.height;selCtx.clearRect(0,0,selectionCanvas.width,selectionCanvas.height);updateMaskInfo();
}
function selectionCoverage(){
  if(!selectionCanvas.width)return 0;const d=selCtx.getImageData(0,0,selectionCanvas.width,selectionCanvas.height).data;let n=0;for(let i=3;i<d.length;i+=4)if(d[i]>8)n++;return n/(selectionCanvas.width*selectionCanvas.height);
}
function maskBBox(maskCanvas=selectionCanvas){
  if(!maskCanvas.width)return null;
  const ctx=maskCanvas.getContext("2d",{willReadFrequently:true}),d=ctx.getImageData(0,0,maskCanvas.width,maskCanvas.height).data,w=maskCanvas.width,h=maskCanvas.height;
  let minX=w,minY=h,maxX=-1,maxY=-1;
  for(let y=0;y<h;y++)for(let x=0;x<w;x++){if(d[(y*w+x)*4+3]>8){if(x<minX)minX=x;if(x>maxX)maxX=x;if(y<minY)minY=y;if(y>maxY)maxY=y}}
  return maxX<0?null:{x:minX,y:minY,w:maxX-minX+1,h:maxY-minY+1};
}
function selectionBBox(){return maskBBox(selectionCanvas)}
function updateMaskInfo(){$("maskCoverage").textContent="选区 "+(selectionCoverage()*100).toFixed(1)+"%"}
function resetWorkHistory(){workHistory=[snapshotWork()];workHistoryIndex=0;updateUndo()}
function snapshotWork(){return{image:workCanvas.toDataURL("image/png"),mask:selectionCanvas.toDataURL("image/png")}}
function pushWorkHistory(){workHistory=workHistory.slice(0,workHistoryIndex+1);workHistory.push(snapshotWork());workHistoryIndex=workHistory.length-1;if(workHistory.length>20){workHistory.shift();workHistoryIndex--}updateUndo()}
function updateUndo(){$("undoImage").disabled=workHistoryIndex<=0;$("redoImage").disabled=workHistoryIndex>=workHistory.length-1}
async function restoreWork(i){
  if(i<0||i>=workHistory.length)return;const s=workHistory[i],im=await imgFromUrl(s.image),mm=await imgFromUrl(s.mask);workHistoryIndex=i;
  workCanvas.width=im.naturalWidth;workCanvas.height=im.naturalHeight;workCtx.clearRect(0,0,workCanvas.width,workCanvas.height);workCtx.drawImage(im,0,0);
  selectionCanvas.width=workCanvas.width;selectionCanvas.height=workCanvas.height;selCtx.clearRect(0,0,selectionCanvas.width,selectionCanvas.height);selCtx.drawImage(mm,0,0);
  floating=null;resetAdjust(false);syncEditorSizeInputs();updateUndo();renderEditor();
}
$("undoImage").onclick=()=>restoreWork(workHistoryIndex-1);$("redoImage").onclick=()=>restoreWork(workHistoryIndex+1);
$("resetDraft").onclick=async()=>{if(!editorSource?.url)return;await openEditorAsset(editorSource)};
$("downloadDraft").onclick=()=>{if(!workCanvas.width)return;const a=document.createElement("a");a.download="draft_"+(editorSource?.name||"image.png");a.href=workCanvas.toDataURL("image/png");a.click()};
$("saveEditor").onclick=async()=>{
  if(!workCanvas.width){notify("请先选择图片。","editor");return}if(floating){notify("请先确定或取消当前 Paste。","editor");return}
  const name=(editorSource?.name||"image").replace(/\.[^.]+$/,"")+"_edit";
  const r=await fetch("/api/save-editor",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({image_b64:dataUrlToB64(workCanvas.toDataURL("image/png")),name,source_url:editorSource?.url})}),j=await r.json();
  if(!r.ok){notify(j.error||"保存失败","editor");return}notify("已保存为新图片 · 原图未修改。右侧图片库已新增结果。","editor");await refreshAssets();
};

function syncEditorSizeInputs(){$("resizeW").value=workCanvas.width||"";$("resizeH").value=workCanvas.height||""}
function resetAdjust(redraw=true){
  for(const [id,v] of [["brightness",100],["contrast",100],["saturation",100],["blur",0],["sharpen",0]]){$(id).value=v;$(id+"Val").textContent=v}
  if(redraw)renderEditor();
}
function adjustmentChanged(){return +$("brightness").value!==100||+$("contrast").value!==100||+$("saturation").value!==100||+$("blur").value!==0||+$("sharpen").value!==0}
function sharpenCanvas(ctx,w,h,amount){
  if(amount<=0||w<3||h<3)return;const im=ctx.getImageData(0,0,w,h),d=im.data,src=new Uint8ClampedArray(d),a=Math.min(.85,amount*.16);
  for(let y=1;y<h-1;y++)for(let x=1;x<w-1;x++){const i=(y*w+x)*4;for(let c=0;c<3;c++){const v=src[i+c]*(1+4*a)-a*(src[i-4+c]+src[i+4+c]+src[i-w*4+c]+src[i+w*4+c]);d[i+c]=Math.max(0,Math.min(255,v))}}ctx.putImageData(im,0,0)
}
function featherMaskCanvas(maskCanvas=selectionCanvas,featherPx=+$("feather").value||0){
  const c=document.createElement("canvas");c.width=maskCanvas.width;c.height=maskCanvas.height;const x=c.getContext("2d");
  if(featherPx)x.filter="blur("+featherPx+"px)";x.drawImage(maskCanvas,0,0);x.filter="none";return c;
}
function constrainedMaskCanvas(maskCanvas=selectionCanvas,featherPx=+$("feather").value||0){
  if(!featherPx)return cloneCanvas(maskCanvas);
  const blur=featherMaskCanvas(maskCanvas,featherPx),out=document.createElement("canvas");
  out.width=maskCanvas.width;out.height=maskCanvas.height;
  const orig=maskCanvas.getContext("2d",{willReadFrequently:true}).getImageData(0,0,out.width,out.height);
  const soft=blur.getContext("2d",{willReadFrequently:true}).getImageData(0,0,out.width,out.height);
  const o=out.getContext("2d"),dst=o.createImageData(out.width,out.height);
  for(let i=0;i<dst.data.length;i+=4){
    const a=Math.round(orig.data[i+3]*soft.data[i+3]/255);
    dst.data[i]=dst.data[i+1]=dst.data[i+2]=255;dst.data[i+3]=a;
  }
  o.putImageData(dst,0,0);return out;
}
function buildAdjustedCanvas(){
  const a=document.createElement("canvas");a.width=workCanvas.width;a.height=workCanvas.height;const x=a.getContext("2d",{willReadFrequently:true});
  x.filter=`brightness(${$("brightness").value}%) contrast(${$("contrast").value}%) saturate(${$("saturation").value}%) blur(${$("blur").value}px)`;x.drawImage(workCanvas,0,0);x.filter="none";sharpenCanvas(x,a.width,a.height,+$("sharpen").value);
  if(selectionCoverage()>0){
    const masked=document.createElement("canvas");masked.width=a.width;masked.height=a.height;const m=masked.getContext("2d");m.drawImage(a,0,0);m.globalCompositeOperation="destination-in";m.drawImage(constrainedMaskCanvas(),0,0);m.globalCompositeOperation="source-over";
    const out=document.createElement("canvas");out.width=a.width;out.height=a.height;const o=out.getContext("2d");o.drawImage(workCanvas,0,0);o.drawImage(masked,0,0);return out;
  }
  return a;
}
["brightness","contrast","saturation","blur","sharpen"].forEach(id=>$(id).oninput=e=>{$(id+"Val").textContent=e.target.value;clearTimeout(adjustTimer);adjustTimer=setTimeout(renderEditor,50)});
$("resetAdjust").onclick=()=>resetAdjust();
$("applyAdjust").onclick=()=>{if(!workCanvas.width||!adjustmentChanged())return;commitWork(buildAdjustedCanvas(),selectionCanvas,"图像调整");resetAdjust(false)};
function commitWork(newCanvas,newMask=selectionCanvas,label="编辑"){
  workCanvas.width=newCanvas.width;workCanvas.height=newCanvas.height;workCtx.clearRect(0,0,workCanvas.width,workCanvas.height);workCtx.drawImage(newCanvas,0,0);
  if(newMask!==selectionCanvas||selectionCanvas.width!==workCanvas.width||selectionCanvas.height!==workCanvas.height){
    const tmp=document.createElement("canvas");tmp.width=workCanvas.width;tmp.height=workCanvas.height;tmp.getContext("2d").drawImage(newMask,0,0,workCanvas.width,workCanvas.height);
    selectionCanvas.width=workCanvas.width;selectionCanvas.height=workCanvas.height;selCtx.clearRect(0,0,workCanvas.width,workCanvas.height);selCtx.drawImage(tmp,0,0);
  }
  syncEditorSizeInputs();pushWorkHistory();renderEditor();notify(label+"完成 · 尚未覆盖原图。","editor");
}

/* 浏览 */
const zoomSelect=$("viewZoom");zoomSelect.add(new Option("自定义","custom"));
function applyViewZoom(){
  if(!workCanvas.width)return;let s;
  if(zoomSelect.value==="fit"){const aw=Math.max(260,editorViewport.clientWidth-36),ah=Math.max(320,window.innerHeight*.68);s=Math.min(1,aw/workCanvas.width,ah/workCanvas.height)}
  else if(zoomSelect.value==="custom")s=currentViewScale;else s=+zoomSelect.value;
  currentViewScale=s;const w=workCanvas.width*s,h=workCanvas.height*s;editorStage.style.width=w+"px";editorStage.style.height=h+"px";
  for(const c of [sourceCanvas,overlayCanvas]){c.style.width=w+"px";c.style.height=h+"px"}
}
zoomSelect.onchange=applyViewZoom;$("zoomOut").onclick=()=>{currentViewScale=Math.max(.05,currentViewScale/1.25);zoomSelect.value="custom";applyViewZoom()};$("zoomIn").onclick=()=>{currentViewScale=Math.min(8,currentViewScale*1.25);zoomSelect.value="custom";applyViewZoom()};window.addEventListener("resize",()=>{if(zoomSelect.value==="fit")applyViewZoom()});

function renderEditor(){
  if(!workCanvas.width){$("editorEmpty").classList.remove("hidden");editorViewport.classList.add("hidden");return}
  $("editorEmpty").classList.add("hidden");editorViewport.classList.remove("hidden");
  sourceCanvas.width=overlayCanvas.width=workCanvas.width;sourceCanvas.height=overlayCanvas.height=workCanvas.height;
  overlayCanvas.style.pointerEvents=mode==="editor"?"auto":"none";
  overlayCanvas.style.cursor=mode==="editor"?"crosshair":"default";
  displayCtx.clearRect(0,0,sourceCanvas.width,sourceCanvas.height);displayCtx.drawImage(adjustmentChanged()?buildAdjustedCanvas():workCanvas,0,0);
  renderOverlay();applyViewZoom();$("editorMeta").textContent=workCanvas.width+"×"+workCanvas.height+" · "+(editorSource?.kind?kindLabel(editorSource.kind):"草稿");updateMaskInfo();
}
let antsPhase=0;
function renderOverlay(){
  overlayCtx.clearRect(0,0,overlayCanvas.width,overlayCanvas.height);
  if(mode!=="editor")return;
  if($("showMask").checked&&selectionCanvas.width){
    const w=selectionCanvas.width,h=selectionCanvas.height,d=selCtx.getImageData(0,0,w,h),o=overlayCtx.createImageData(w,h),src=d.data,dst=o.data;
    for(let i=0;i<src.length;i+=4){const a=src[i+3];if(a){dst[i]=255;dst[i+1]=35;dst[i+2]=65;dst[i+3]=Math.round(a*.20)}}
    for(let y=0;y<h;y++)for(let x=0;x<w;x++){
      const p=y*w+x,i=p*4,a=src[i+3];if(a<=8)continue;
      const edge=x===0||y===0||x===w-1||y===h-1||
        src[(p-1)*4+3]<=8||src[(p+1)*4+3]<=8||src[(p-w)*4+3]<=8||src[(p+w)*4+3]<=8;
      if(edge){const white=((x+y+antsPhase)>>2)%2===0;dst[i]=dst[i+1]=dst[i+2]=white?255:15;dst[i+3]=255}
    }
    overlayCtx.putImageData(o,0,0);
  }
  if(floating){overlayCtx.save();overlayCtx.globalAlpha=floating.opacity??1;overlayCtx.drawImage(floating.canvas,floating.x,floating.y,floating.w,floating.h);overlayCtx.strokeStyle="#2477d4";overlayCtx.lineWidth=Math.max(2,workCanvas.width/500);overlayCtx.setLineDash([7,5]);overlayCtx.lineDashOffset=-antsPhase;overlayCtx.strokeRect(floating.x,floating.y,floating.w,floating.h);overlayCtx.restore()}
}
setInterval(()=>{if(mode==="editor"&&selectionCanvas.width&&$("showMask").checked){antsPhase=(antsPhase+1)%16;renderOverlay()}},180);
$("showMask").onchange=renderOverlay;$("brush").oninput=e=>$("brushVal").textContent=e.target.value;$("feather").oninput=e=>$("featherVal").textContent=e.target.value;
function selectTool(t){selectionTool=t;["rect","ellipse","paint","erase","wandAdd","wandSub"].forEach(k=>$(k+"Tool").classList.toggle("active",k===t))}
["rect","ellipse","paint","erase","wandAdd","wandSub"].forEach(k=>$(k+"Tool").onclick=()=>selectTool(k));
function canvasPoint(ev){const r=overlayCanvas.getBoundingClientRect();return{x:(ev.clientX-r.left)*overlayCanvas.width/r.width,y:(ev.clientY-r.top)*overlayCanvas.height/r.height}}
function drawSelectionStroke(a,b){
  selCtx.save();selCtx.lineWidth=+$("brush").value;selCtx.lineCap="round";selCtx.lineJoin="round";selCtx.strokeStyle="#fff";
  if(selectionTool==="erase")selCtx.globalCompositeOperation="destination-out";
  selCtx.beginPath();selCtx.moveTo(a.x,a.y);selCtx.lineTo(b.x,b.y);selCtx.stroke();selCtx.restore();renderOverlay();updateMaskInfo();
}
function drawSelectionShape(a,b){
  if(shapeBase)selCtx.putImageData(shapeBase,0,0);const x=Math.min(a.x,b.x),y=Math.min(a.y,b.y),w=Math.abs(a.x-b.x),h=Math.abs(a.y-b.y);selCtx.fillStyle="#fff";
  if(selectionTool==="rect")selCtx.fillRect(x,y,w,h);else{selCtx.beginPath();selCtx.ellipse(x+w/2,y+h/2,Math.max(.5,w/2),Math.max(.5,h/2),0,0,Math.PI*2);selCtx.fill()}renderOverlay();updateMaskInfo();
}
function magicWand(p,add){
  if(!workCanvas.width)return;const w=workCanvas.width,h=workCanvas.height,x=Math.max(0,Math.min(w-1,Math.floor(p.x))),y=Math.max(0,Math.min(h-1,Math.floor(p.y))),tol=Math.max(0,+$("wandTolerance").value||0);
  const pix=workCtx.getImageData(0,0,w,h).data,mask=selCtx.getImageData(0,0,w,h),md=mask.data,seed=(y*w+x)*4,ref=[pix[seed],pix[seed+1],pix[seed+2],pix[seed+3]],target=add?255:0;
  const ok=i=>Math.max(Math.abs(pix[i]-ref[0]),Math.abs(pix[i+1]-ref[1]),Math.abs(pix[i+2]-ref[2]),Math.abs(pix[i+3]-ref[3]))<=tol;
  if($("wandContiguous").checked){const seen=new Uint8Array(w*h),q=new Int32Array(w*h);let head=0,tail=0;q[tail++]=y*w+x;seen[y*w+x]=1;while(head<tail){const n=q[head++],i=n*4;if(!ok(i))continue;md[i]=md[i+1]=md[i+2]=255;md[i+3]=target;const nx=n%w,ny=(n/w)|0;for(const z of [n-1,n+1,n-w,n+w]){if(z<0||z>=w*h||seen[z])continue;const zx=z%w,zy=(z/w)|0;if(Math.abs(zx-nx)+Math.abs(zy-ny)!==1)continue;seen[z]=1;q[tail++]=z}}}
  else for(let n=0;n<w*h;n++){const i=n*4;if(ok(i)){md[i]=md[i+1]=md[i+2]=255;md[i+3]=target}}
  selCtx.putImageData(mask,0,0);renderOverlay();updateMaskInfo();
}
overlayCanvas.onpointerdown=e=>{
  if(!workCanvas.width)return;const p=canvasPoint(e);drawing=true;overlayCanvas.setPointerCapture(e.pointerId);
  if(floating){dragStart={p,x:floating.x,y:floating.y};return}
  if(selectionTool==="wandAdd"||selectionTool==="wandSub"){drawing=false;magicWand(p,selectionTool==="wandAdd");return}
  lastPoint=p;if(selectionTool==="paint"||selectionTool==="erase")drawSelectionStroke(p,p);
  else{shapeStart=p;shapeBase=selCtx.getImageData(0,0,selectionCanvas.width,selectionCanvas.height);selCtx.clearRect(0,0,selectionCanvas.width,selectionCanvas.height);drawSelectionShape(shapeStart,p)}
};
overlayCanvas.onpointermove=e=>{
  if(!drawing)return;const p=canvasPoint(e);
  if(floating){floating.x=dragStart.x+(p.x-dragStart.p.x);floating.y=dragStart.y+(p.y-dragStart.p.y);renderOverlay();return}
  if(selectionTool==="paint"||selectionTool==="erase"){drawSelectionStroke(lastPoint,p);lastPoint=p}else drawSelectionShape(shapeStart,p)
};
overlayCanvas.onpointerup=()=>{drawing=false;shapeStart=null;shapeBase=null};overlayCanvas.onpointercancel=()=>{drawing=false;shapeStart=null;shapeBase=null};
$("selectAll").onclick=()=>{selCtx.fillStyle="#fff";selCtx.fillRect(0,0,selectionCanvas.width,selectionCanvas.height);renderOverlay();updateMaskInfo()};
$("clearMask").onclick=()=>{selCtx.clearRect(0,0,selectionCanvas.width,selectionCanvas.height);renderOverlay();updateMaskInfo()};
$("invertMask").onclick=()=>{if(!selectionCanvas.width)return;const im=selCtx.getImageData(0,0,selectionCanvas.width,selectionCanvas.height);for(let i=0;i<im.data.length;i+=4){const a=255-im.data[i+3];im.data[i]=im.data[i+1]=im.data[i+2]=255;im.data[i+3]=a}selCtx.putImageData(im,0,0);renderOverlay();updateMaskInfo()};

/* Copy / Cut / Paste 跨图片剪贴板 */
function copySelectionToClipboard(cut=false){
  const b=selectionBBox();if(!b){notify("请先选择区域。","editor");return}
  const c=document.createElement("canvas");c.width=b.w;c.height=b.h;const x=c.getContext("2d",{willReadFrequently:true});x.drawImage(workCanvas,b.x,b.y,b.w,b.h,0,0,b.w,b.h);
  const mask=document.createElement("canvas");mask.width=b.w;mask.height=b.h;mask.getContext("2d").drawImage(selectionCanvas,b.x,b.y,b.w,b.h,0,0,b.w,b.h);x.globalCompositeOperation="destination-in";x.drawImage(mask,0,0);x.globalCompositeOperation="source-over";
  clipboard={canvas:c,w:b.w,h:b.h,sourceName:editorSource?.name||"image",originX:b.x,originY:b.y};clipboardControls();
  if(cut){workCtx.save();workCtx.globalCompositeOperation="destination-out";workCtx.drawImage(selectionCanvas,0,0);workCtx.restore();pushWorkHistory();renderEditor();notify("Cut 完成 · 只修改当前草稿，原图仍保留。","editor")}
}
$("copySelection").onclick=()=>copySelectionToClipboard(false);$("cutSelection").onclick=()=>copySelectionToClipboard(true);
function clipboardControls(){$("clipboardInfo").textContent=clipboard?("剪贴板："+clipboard.w+"×"+clipboard.h+" · "+clipboard.sourceName):"剪贴板为空";$("pasteClipboard").disabled=!clipboard}
function startPaste(){
  if(!clipboard||!workCanvas.width)return;floating={canvas:clipboard.canvas,w:clipboard.w,h:clipboard.h,x:Math.max(0,(workCanvas.width-clipboard.w)/2),y:Math.max(0,(workCanvas.height-clipboard.h)/2),aspect:clipboard.w/clipboard.h,opacity:1};
  $("pasteW").value=Math.round(floating.w);$("pasteH").value=Math.round(floating.h);$("pasteOpacity").value=100;$("pasteOpacityVal").textContent=100;$("pasteControls").classList.remove("hidden");renderOverlay();notify("Paste 预览 · 拖动位置、调整宽高或透明度；确定前不会写入草稿。","editor");
}
$("pasteClipboard").onclick=startPaste;
$("pasteW").oninput=()=>{if(!floating)return;let w=Math.max(1,+$("pasteW").value||1);floating.w=w;if($("pasteLockAspect").checked){floating.h=Math.max(1,Math.round(w/floating.aspect));$("pasteH").value=Math.round(floating.h)}renderOverlay()};
$("pasteH").oninput=()=>{if(!floating)return;let h=Math.max(1,+$("pasteH").value||1);floating.h=h;if($("pasteLockAspect").checked){floating.w=Math.max(1,Math.round(h*floating.aspect));$("pasteW").value=Math.round(floating.w)}renderOverlay()};
$("pasteOpacity").oninput=e=>{if(!floating)return;$("pasteOpacityVal").textContent=e.target.value;floating.opacity=+e.target.value/100;renderOverlay()};
$("applyPaste").onclick=()=>{if(!floating)return;workCtx.save();workCtx.globalAlpha=floating.opacity??1;workCtx.drawImage(floating.canvas,floating.x,floating.y,floating.w,floating.h);workCtx.restore();floating=null;$("pasteControls").classList.add("hidden");pushWorkHistory();renderEditor();notify("Paste 已写入草稿 · 原图仍未修改。","editor")};
$("cancelPaste").onclick=()=>{floating=null;$("pasteControls").classList.add("hidden");renderOverlay()};

/* 几何 */
$("resizeW").oninput=()=>{if(workCanvas.width&&$("lockAspect").checked)$("resizeH").value=Math.max(1,Math.round(+$("resizeW").value*workCanvas.height/workCanvas.width))};
$("resizeH").oninput=()=>{if(workCanvas.height&&$("lockAspect").checked)$("resizeW").value=Math.max(1,Math.round(+$("resizeH").value*workCanvas.width/workCanvas.height))};
$("applyResize").onclick=()=>{if(!workCanvas.width)return;const w=Math.max(1,+$("resizeW").value|0),h=Math.max(1,+$("resizeH").value|0),c=document.createElement("canvas"),m=document.createElement("canvas");c.width=w;c.height=h;m.width=w;m.height=h;c.getContext("2d").drawImage(workCanvas,0,0,w,h);m.getContext("2d").drawImage(selectionCanvas,0,0,w,h);commitWork(c,m,"实际像素缩放")};
function rotated(src,deg,smooth=true){const r=deg*Math.PI/180,cs=Math.abs(Math.cos(r)),sn=Math.abs(Math.sin(r)),w=Math.ceil(src.width*cs+src.height*sn),h=Math.ceil(src.width*sn+src.height*cs),c=document.createElement("canvas");c.width=w;c.height=h;const x=c.getContext("2d");x.imageSmoothingEnabled=smooth;x.translate(w/2,h/2);x.rotate(r);x.drawImage(src,-src.width/2,-src.height/2);return c}
function rotateDraft(deg){if(!workCanvas.width||!deg)return;commitWork(rotated(workCanvas,deg,true),rotated(selectionCanvas,deg,false),"旋转 "+deg+"°")}
$("rotateLeft").onclick=()=>rotateDraft(-90);$("rotateRight").onclick=()=>rotateDraft(90);$("applyRotate").onclick=()=>rotateDraft(+$("rotateAngle").value||0);
$("cropToSelection").onclick=()=>{const b=selectionBBox();if(!b){notify("请先选择裁剪区域。","editor");return}const c=document.createElement("canvas"),m=document.createElement("canvas");c.width=m.width=b.w;c.height=m.height=b.h;c.getContext("2d").drawImage(workCanvas,b.x,b.y,b.w,b.h,0,0,b.w,b.h);m.getContext("2d").drawImage(selectionCanvas,b.x,b.y,b.w,b.h,0,0,b.w,b.h);commitWork(c,m,"裁剪")};

/* AI 局部编辑 */
function selectionToBW(maskCanvas=selectionCanvas){
  const c=document.createElement("canvas");c.width=maskCanvas.width;c.height=maskCanvas.height;const x=c.getContext("2d");
  x.fillStyle="#000";x.fillRect(0,0,c.width,c.height);
  const alpha=x.createImageData(c.width,c.height),md=maskCanvas.getContext("2d",{willReadFrequently:true}).getImageData(0,0,c.width,c.height).data;
  for(let i=0;i<md.length;i+=4){const v=md[i+3];alpha.data[i]=alpha.data[i+1]=alpha.data[i+2]=v;alpha.data[i+3]=255}
  x.putImageData(alpha,0,0);return c;
}
function canvasCoverage(maskCanvas){
  if(!maskCanvas.width)return 0;const d=maskCanvas.getContext("2d",{willReadFrequently:true}).getImageData(0,0,maskCanvas.width,maskCanvas.height).data;let n=0;
  for(let i=3;i<d.length;i+=4)if(d[i]>8)n++;return n/(maskCanvas.width*maskCanvas.height);
}
function safeLocalSizeFor(canvas){let w=canvas.width,h=canvas.height,s=1,t=(w/32)*(h/32)*2;if(t>1450)s=Math.sqrt(1450/t);if(Math.max(w*s,h*s)>1152)s*=1152/Math.max(w*s,h*s);return[round32(w*s),round32(h*s)]}
function roundLocal32(v){return Math.max(256,Math.min(1152,Math.round(v/32)*32))}
function safeLocalCropSize(w,h){
  const maxSide=Math.max(w,h),minSide=Math.max(1,Math.min(w,h));
  const tokenScale=Math.sqrt(1450/Math.max(1,(w/32)*(h/32)*2));
  const sideScale=1152/maxSide;
  const maxScale=Math.min(tokenScale,sideScale);
  const desiredScale=Math.max(1,640/maxSide,320/minSide);
  let scale=Math.min(desiredScale,maxScale);
  if(maxScale<1)scale=maxScale;
  let tw=roundLocal32(w*scale),th=roundLocal32(h*scale);
  while(((tw/32)*(th/32)*2>1450||Math.max(tw,th)>1152)&&(tw>256||th>256)){
    if(tw>=th&&tw>256)tw-=32;else if(th>256)th-=32;else break;
  }
  return[tw,th];
}
function cropCanvas(src,rect){
  const c=document.createElement("canvas");c.width=rect.w;c.height=rect.h;
  c.getContext("2d").drawImage(src,rect.x,rect.y,rect.w,rect.h,0,0,rect.w,rect.h);return c;
}
function centeredSpan(start,size,target,max){
  target=Math.min(max,Math.max(size,Math.ceil(target)));
  let out=Math.floor(start+size/2-target/2);
  out=Math.max(0,Math.min(max-target,out));return{start:out,size:target};
}
function normalizeCropAspect(rect,W,H){
  let {x,y,w,h}=rect,r=w/h;
  if(r<0.65){const s=centeredSpan(x,w,h*0.65,W);x=s.start;w=s.size}
  else if(r>1.54){const s=centeredSpan(y,h,w/1.54,H);y=s.start;h=s.size}
  return{x,y,w,h};
}
function alignCropRect(rect,W,H,align=8){
  const x0=Math.max(0,Math.floor(rect.x/align)*align),y0=Math.max(0,Math.floor(rect.y/align)*align);
  const x1=Math.min(W,Math.ceil((rect.x+rect.w)/align)*align),y1=Math.min(H,Math.ceil((rect.y+rect.h)/align)*align);
  return{x:x0,y:y0,w:Math.max(1,x1-x0),h:Math.max(1,y1-y0)};
}
function planLocalAiRegion(sourceCanvas,maskCanvas,featherPx){
  const W=sourceCanvas.width,H=sourceCanvas.height,bbox=maskBBox(maskCanvas);if(!bbox)return null;
  const pad=Math.max(48,Math.ceil(Math.max(bbox.w,bbox.h)*0.25),Math.ceil(featherPx*2+16));
  let x0=Math.max(0,bbox.x-pad),y0=Math.max(0,bbox.y-pad),x1=Math.min(W,bbox.x+bbox.w+pad),y1=Math.min(H,bbox.y+bbox.h+pad);
  let crop=normalizeCropAspect({x:x0,y:y0,w:x1-x0,h:y1-y0},W,H);
  crop=alignCropRect(crop,W,H,8);
  const cropPercent=crop.w*crop.h/(W*H);
  const useFull=cropPercent>=0.72;
  if(useFull)crop={x:0,y:0,w:W,h:H};
  const target=useFull?safeLocalSizeFor(sourceCanvas):safeLocalCropSize(crop.w,crop.h);
  return{strategy:useFull?"full":"crop",bbox,crop,cropPercent:useFull?1:cropPercent,padding:pad,target};
}
function composeCropCandidate(sourceSnap,aiImg,crop){
  const c=cloneCanvas(sourceSnap),x=c.getContext("2d");
  x.drawImage(aiImg,crop.x,crop.y,crop.w,crop.h);return c;
}
function hardMergeAi(aiCandidate,sourceSnap,maskSnap,featherPx){
  const W=sourceSnap.width,H=sourceSnap.height,out=document.createElement("canvas"),ai=document.createElement("canvas");
  out.width=ai.width=W;out.height=ai.height=H;
  const ox=out.getContext("2d",{willReadFrequently:true}),ax=ai.getContext("2d",{willReadFrequently:true});
  ox.drawImage(sourceSnap,0,0);ax.drawImage(aiCandidate,0,0,W,H);
  const src=ox.getImageData(0,0,W,H),ed=ax.getImageData(0,0,W,H);
  const raw=maskSnap.getContext("2d",{willReadFrequently:true}).getImageData(0,0,W,H);
  const eff=constrainedMaskCanvas(maskSnap,featherPx).getContext("2d",{willReadFrequently:true}).getImageData(0,0,W,H);
  const dst=ox.createImageData(W,H);let outsideChanged=0,insideChanged=0;
  for(let i=0;i<dst.data.length;i+=4){
    const a=eff.data[i+3]/255;
    for(let c=0;c<4;c++)dst.data[i+c]=a<=0?src.data[i+c]:a>=1?ed.data[i+c]:Math.round(src.data[i+c]*(1-a)+ed.data[i+c]*a);
    const changed=dst.data[i]!==src.data[i]||dst.data[i+1]!==src.data[i+1]||dst.data[i+2]!==src.data[i+2]||dst.data[i+3]!==src.data[i+3];
    if(raw.data[i+3]===0&&changed)outsideChanged++;
    if(raw.data[i+3]>0&&changed)insideChanged++;
  }
  ox.putImageData(dst,0,0);return{canvas:out,outsideChanged,insideChanged};
}
function localPlanText(plan,sourceSnap){
  const b=plan.bbox,c=plan.crop,[tw,th]=plan.target;
  const strategy=plan.strategy==="crop"?"局部裁剪":"整图回退";
  return strategy+" · 原图 "+sourceSnap.width+"×"+sourceSnap.height+
    " · Mask bbox "+b.w+"×"+b.h+" @ "+b.x+","+b.y+
    " · 输入区域 "+c.w+"×"+c.h+" @ "+c.x+","+c.y+
    " · Qwen "+tw+"×"+th;
}
$("runLocalAi").onclick=async()=>{
  if(!workCanvas.width){notify("请先选择图片。","editor");return}
  const coverage=selectionCoverage();if(coverage<=0){notify("请先选择要 AI 编辑的区域。","editor");return}
  const user=$("localAiPrompt").value.trim();if(!user){notify("请输入 AI 局部编辑指令。","editor");return}
  const sourceSnap=cloneCanvas(workCanvas),maskSnap=cloneCanvas(selectionCanvas),featherPx=+$("feather").value||0;
  const plan=planLocalAiRegion(sourceSnap,maskSnap,featherPx);if(!plan){notify("无法计算 Mask 区域。","editor");return}
  const sourceKey=editorSource?.url||editorSource?.name||"draft",historyAtStart=workHistoryIndex,[w,h]=plan.target;
  const qwenSource=cropCanvas(sourceSnap,plan.crop),qwenMask=cropCanvas(maskSnap,plan.crop);
  const prompt="<image1>是原图中包含目标的工作区域。<image2>是同一区域的黑白位置遮罩：白色区域是唯一允许修改的区域，黑色区域禁止修改。"+
    user+"。严格保持黑色区域对应的构图、颜色、纹理和透明度不变；不要改变工作区域之外不存在的内容。";
  const btn=$("runLocalAi"),oldText=btn.textContent;btn.disabled=true;btn.textContent="AI 编辑中…";
  notify("AI 局部编辑中…\nMask "+(coverage*100).toFixed(1)+"% · 原图与 Mask 已冻结。\n"+localPlanText(plan,sourceSnap)+
    (plan.strategy==="crop"?"\n仅把局部区域送给 Qwen，完成后贴回原图。":"\n选区分布太广，自动回退到整图送模。"),"editor");
  try{
    const r=await fetch("/api/mask-edit",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({
      prompt,size:w+"x"+h,steps:+$("localAiSteps").value||20,seed:+$("localAiSeed").value||42,
      image_b64:dataUrlToB64(qwenSource.toDataURL("image/png")),mask_b64:dataUrlToB64(selectionToBW(qwenMask).toDataURL("image/png")),
      source_size:qwenSource.width+"x"+qwenSource.height,full_source_size:sourceSnap.width+"x"+sourceSnap.height,
      mask_percent:+(coverage*100).toFixed(2),local_strategy:plan.strategy,
      mask_bbox:[plan.bbox.x,plan.bbox.y,plan.bbox.w,plan.bbox.h],
      crop_rect:[plan.crop.x,plan.crop.y,plan.crop.w,plan.crop.h],
      crop_percent:+(plan.cropPercent*100).toFixed(2)
    })}),j=await r.json();
    if(!r.ok)throw new Error(j.error||"AI 编辑失败");
    if((editorSource?.url||editorSource?.name||"draft")!==sourceKey||workHistoryIndex!==historyAtStart){
      notify("AI 已生成完成，但生成期间当前草稿发生了变化，所以结果没有自动应用。请重新点击 AI 编辑选区。","editor");return;
    }
    const im=await imgFromUrl("data:image/png;base64,"+j.b64_json);
    const candidate=composeCropCandidate(sourceSnap,im,plan.crop),merged=hardMergeAi(candidate,sourceSnap,maskSnap,featherPx);
    if(merged.outsideChanged!==0)throw new Error("安全检查失败：Mask 外检测到 "+merged.outsideChanged+" 个像素变化，结果已拒绝应用");
    commitWork(merged.canvas,maskSnap,"AI 局部编辑");
    const base=(editorSource?.name||"image").replace(/\.[^.]+$/,"");
    const saveReq=await fetch("/api/save-editor",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({
      image_b64:dataUrlToB64(merged.canvas.toDataURL("image/png")),
      name:base+"_AI局部编辑",
      source_url:editorSource?.url
    })}),saved=await saveReq.json();
    if(!saveReq.ok)throw new Error(saved.error||"AI结果自动保存失败");
    await refreshAssets();
    const savedAsset=assets.find(a=>a.url===saved.url)||{url:saved.url,name:saved.name,kind:"edited"};
    const savedImg=await imgFromUrl(saved.url);
    editorSource={...savedAsset,w:savedImg.naturalWidth,h:savedImg.naturalHeight,img:savedImg};

    selectionCanvas.width=workCanvas.width;selectionCanvas.height=workCanvas.height;
    selCtx.clearRect(0,0,selectionCanvas.width,selectionCanvas.height);
    floating=null;shapeStart=null;shapeBase=null;drawing=false;
    resetAdjust(false);resetWorkHistory();syncEditorSizeInputs();
    $("editorTitle").textContent=saved.name;
    renderEditor();renderAssets();

    const perf=formatPerf(j.perf);$("localAiPerf").textContent=perf;
    notify("AI 局部编辑完成并已自动保存到右侧图片库。\n已切换到新图片："+saved.name+
      "\n旧图仍保留；旧 Mask 已清空；编辑历史已从新图片重新开始。"+
      "\n"+localPlanText(plan,sourceSnap)+
      "\n本次 Mask "+(coverage*100).toFixed(1)+"% · Mask 外像素安全检查：0 个变化 · Mask 内变化 "+merged.insideChanged+" 个像素"+
      (featherPx?" · 羽化仅向 Mask 内部过渡":"")+"\n"+perf,"editor");
  }catch(e){notify("AI 编辑失败："+e.message,"editor")}
  finally{btn.disabled=false;btn.textContent=oldText}
};

/* 最近生成 */
async function loadHistory(){
  try{const j=await fetch("/api/history",{cache:"no-store"}).then(r=>r.json()),box=$("history");box.innerHTML="";if(!j.items.length){box.innerHTML="<div class='fileInfo'>暂无记录</div>";return}
    j.items.forEach(x=>{const d=document.createElement("div");d.className="histItem";const del=document.createElement("button");del.className="histDelete";del.textContent="删除";del.onclick=e=>{e.stopPropagation();deleteHistory(x.output_url)};
      d.innerHTML="<img src='"+x.output_url+"'><div class='histMeta'>"+escapeHtml(x.mode||"生成")+" · "+escapeHtml(x.size||x.source_size||"")+"</div>";d.append(del);d.onclick=()=>openEditorByUrl(x.output_url);box.append(d)})
  }catch(e){}
}
async function deleteHistory(url){if(!confirm("删除这个生成结果？"))return;await fetch("/api/delete-asset",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url})});await Promise.all([loadHistory(),refreshAssets()])}
$("refreshHistory").onclick=loadHistory;

/* 服务状态 */
async function refreshStatus(){
  try{const s=await fetch("/api/status",{cache:"no-store"}).then(r=>r.json());qwenBadge.textContent=s.qwen_ok?"Qwen 在线":"Qwen 离线";qwenBadge.className="badge "+(s.qwen_ok?"ok":"off");memBadge.textContent="Swap "+(s.swap_mb==null?"—":(s.swap_mb/1024).toFixed(1)+" GB")+" · 空闲 "+(s.memory_free_pct??"—")+"%"}catch(e){qwenBadge.textContent="服务离线";qwenBadge.className="badge off"}
}
$("refreshStatus").onclick=refreshStatus;

clipboardControls();refreshStatus();loadHistory();refreshAssets();autoGenSize();setMode("generate");notify("就绪。生成或编辑过程中的状态都会保留在这里；右侧列表可回看历史提示。","gen",false);