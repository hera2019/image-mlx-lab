(()=>{ 
  const KEY="imageMlxLab.uiLanguage";
  let lang=(localStorage.getItem(KEY)||"zh")==="en"?"en":"zh";
  const originalText=new WeakMap(),originalAttrs=new WeakMap();
  const EN={
    "Qwen-Image-2.1 MLX · 本机生成与非破坏式图片编辑":"Qwen-Image-2.1 MLX · Local generation and non-destructive image editing",
    "模型检查中…":"Checking model…","内存 —":"Memory —","刷新":"Refresh",
    "文生图":"Text to Image","图生图":"Image to Image","指令编辑":"True Edit","图片编辑":"Image Editor",
    "适合窗口":"Fit","撤销":"Undo","重做":"Redo","↶ 撤销":"↶ Undo","↷ 重做":"↷ Redo","恢复原图":"Restore Original","保存为新图":"Save as New",
    "覆盖当前图":"Overwrite Current","下载当前草稿":"Download Draft",
    "提示词":"Prompt","描述你想生成的图片":"Describe the image you want to generate",
    "透明 RGBA 背景":"Transparent RGBA background","高质量":"High quality","主体完整":"Complete subject",
    "图生图 / 相似变体":"Image to Image / Variations",
    "根据原图生成相似的新版本，适合风格、构图或整体变化；不适合“只改衣服颜色”这类精确属性修改。需要明确修改指定内容时，请使用「指令编辑 / True Edit」。主图默认使用中间当前图片，也可以直接载入新图。":"Create a related new version from the source image. Best for style, composition, or overall changes; not for precise changes such as “only change the clothing color.” Use True Edit for targeted edits. The current center image is used by default, or you can load another image.",
    "载入主图":"Load Main Image","尚未选择主图":"No main image selected","目标描述":"Target Description",
    "希望当前主图变成什么样":"Describe how you want the current image to change",
    "指令编辑 / True Edit":"True Edit",
    "按文字指令修改现有图片，例如改衣服颜色、改材质、替换指定对象或调整局部属性；更适合明确的编辑任务。主图默认使用中间当前图片，右侧点击任意正式图片即可切换。":"Edit an existing image with explicit instructions, such as changing a clothing color, material, object, or local property. Best for targeted edits. The current center image is used by default; click any final image on the right to switch.",
    "＋ 添加参考图到队列":"＋ Add Reference Images","队列可保存多张；当前最多启用 3 张额外参考图（加主图共 4 张）。":"The queue can hold multiple images; up to 3 extra references can be active at once (4 images total including the main image).",
    "编辑指令":"Edit Instruction","例如：保持角色完全一致，只把尾巴改成橙红色。":"Example: keep the character identical and only change the tail to orange-red.",
    "保持构图":"Keep Composition","角色一致":"Keep Identity","局部约束":"Target Only",
    "生成设置":"Generation Settings","分辨率":"Resolution","自动安全尺寸":"Auto Safe Size","自定义":"Custom",
    "宽":"Width","高":"Height","视觉 token：—":"Visual tokens: —","随机 Seed":"Random Seed",
    "重新计算安全尺寸":"Recalculate Safe Size","开始生成":"Generate"
  };  Object.assign(EN,{
    "＋ 载入图片":"＋ Load Images","选区 / Mask":"Selection / Mask","矩形":"Rectangle","椭圆":"Ellipse",
    "▭ 矩形":"▭ Rectangle","◯ 椭圆":"◯ Ellipse","〰 套索＋":"〰 Lasso +","〰 套索－":"〰 Lasso −",
    "✏️ 画笔":"✏️ Brush","⌫ 擦除":"⌫ Erase","🪄 魔棒＋":"🪄 Magic Wand +","🪄 魔棒－":"🪄 Magic Wand −",
    "套索＋":"Lasso +","套索－":"Lasso −","画笔":"Brush","擦除":"Erase","魔棒＋":"Magic Wand +","魔棒－":"Magic Wand −",
    "魔棒容差":"Wand Tolerance","连续区域":"Contiguous","显示 Mask":"Show Mask","全选":"Select All","反选":"Invert",
    "清除选区":"Clear Selection","边界":"Boundary","扩展":"Expand","收缩":"Contract",
    "扩展适合 AI 去遮挡时吃掉残边；收缩可避免修改碰到主体边缘。":"Expand helps remove leftover edges when AI removes an obstruction; Contract protects nearby subject edges.",
    "边缘羽化":"Edge Feather","选区 0%":"Selection 0%",
    "修复 / 仿制":"Heal / Clone","克隆图章":"Clone Stamp","修复画笔":"Healing Brush","🧬 克隆图章":"🧬 Clone Stamp","🩹 修复画笔":"🩹 Healing Brush","修复笔刷":"Repair Brush",
    "克隆图章：⌥ Option / Alt + 点击设置取样点，然后在目标区域涂抹。":"Clone Stamp: hold ⌥ Option / Alt and click to set a source point, then paint over the target area.",
    "清除克隆取样点":"Clear Clone Source",
    "修复画笔适合小污点、灰尘和细划痕；复杂纹理优先用克隆图章或 AI 局部编辑。":"Healing Brush works best for small spots, dust, and fine scratches; use Clone Stamp or AI Local Edit for complex textures.",
    "复制 / 剪切 / 粘贴":"Copy / Cut / Paste","剪贴板为空":"Clipboard is empty","按比例缩放":"Lock aspect ratio","透明度":"Opacity",
    "确定粘贴":"Apply Paste","取消":"Cancel","几何 / 尺寸":"Geometry / Size","旋转角度":"Rotate by Angle","缩放保持比例":"Keep aspect ratio",
    "应用实际像素尺寸":"Apply Pixel Size","裁剪到选区外框":"Crop to Selection Bounds",
    "亮度 / 色彩 / 清晰度":"Brightness / Color / Clarity","亮度":"Brightness","对比度":"Contrast","饱和度":"Saturation",
    "模糊":"Blur","锐化":"Sharpen","有选区时自动只作用于选区；没有选区时作用于整张图片。":"With a selection, adjustments affect only the selection; otherwise they affect the whole image.",
    "重置预览":"Reset Preview","应用":"Apply","AI 局部编辑":"AI Local Edit",
    "使用中间当前图片 + 当前 Mask。最终仍由冻结的 full-size Mask 硬合成，Mask 外像素不得变化。":"Uses the current center image and Mask. The final result is composited with the frozen full-size Mask, so pixels outside the Mask must remain unchanged.",
    "上下文":"Context","自动（推荐）":"Auto (Recommended)","局部优先（快）":"Local First (Fast)","局部 + 整图参考":"Local + Full Reference","整图（慢）":"Full Image (Slow)",
    "自动：普通局部修改优先裁剪；遮挡恢复 / 补全等任务会增加整图参考。":"Auto: local edits prefer a crop; obstruction recovery / completion adds a full-image reference.",
    "例如：去掉选区内的遮挡物，恢复主体原来的结构。":"Example: remove the obstruction inside the selection and restore the original structure.",
    "AI 编辑选区":"AI Edit Selection"
  });  Object.assign(EN,{
    "当前主图":"Current Main Image","右侧点击图片即可切换；顶部模式只改变左栏":"Click an image on the right to switch; top modes only change the left panel",
    "从右侧图片库选择图片，或在左侧载入 / 生成":"Choose an image from the library on the right, or load / generate one on the left",
    "图片库":"Image Library","始终存在 · 点击切换中间主图":"Always available · click to switch the center image",
    "正式图片":"Final Images","全部（含中间结果）":"All (incl. intermediates)","生成":"Generated","载入":"Loaded","编辑保存":"Saved Edits","中间结果":"Intermediates",
    "状态与提示":"Status and Notices","状态 / 提示":"Status / Notices",
    "当前图片有未保存修改":"Current image has unsaved changes","切换图片前，请选择如何处理当前草稿。":"Choose what to do with the current draft before switching images.",
    "保存为新图并切换":"Save as New and Switch","覆盖当前图并切换":"Overwrite and Switch","丢弃修改并切换":"Discard and Switch",
    "模型设置":"Model Settings","正在读取模型状态…":"Reading model status…","跳过内存预检（高级）":"Skip memory preflight (advanced)",
    "内存预检会在可用内存不足时拒绝加载模型。跳过后可以强行加载，但可能大量使用 swap、变得很慢甚至卡死。":"The memory preflight blocks model loading when free memory is too low. Skipping it forces a load attempt, which may use heavy swap, become very slow, or make the system unresponsive.",
    "应用并重新加载模型":"Apply and Reload Model","界面语言":"Interface language",
    "模型设置：选择 4-bit / 8-bit":"Model settings: choose 4-bit / 8-bit"
  });
  const ZH_BY_EN=Object.fromEntries(Object.entries(EN).map(([zh,en])=>[en,zh]));
  function ui(zh,en){return lang==="en"?en:zh}
  function translatedRaw(raw,targetLang){
    const trim=raw.trim();
    if(targetLang==="en"){const out=EN[trim];return out?raw.replace(trim,out):raw}
    const out=ZH_BY_EN[trim];return out?raw.replace(trim,out):raw;
  }
  function translateTextNode(node){
    if(!originalText.has(node))originalText.set(node,node.nodeValue);
    node.nodeValue=translatedRaw(originalText.get(node),lang);
  }
  function applyStatic(root=document.body){
    const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
    let node;while((node=walker.nextNode())){
      const tag=node.parentElement?.tagName;if(tag==="SCRIPT"||tag==="STYLE")continue;translateTextNode(node);
    }
    for(const el of root.querySelectorAll("[placeholder],[title],[aria-label]")){
      if(!originalAttrs.has(el))originalAttrs.set(el,{placeholder:el.getAttribute("placeholder"),title:el.getAttribute("title"),aria:el.getAttribute("aria-label")});
      const orig=originalAttrs.get(el);
      for(const [attr,key] of [["placeholder","placeholder"],["title","title"],["aria-label","aria"]]){
        const base=orig[key];if(base==null)continue;el.setAttribute(attr,translatedRaw(base,lang));
      }
    }
    document.documentElement.lang=lang==="en"?"en":"zh-CN";
  }  function setLanguage(next){
    lang=next==="en"?"en":"zh";localStorage.setItem(KEY,lang);applyStatic();
    const sel=document.getElementById("uiLanguage");if(sel)sel.value=lang;
    document.dispatchEvent(new CustomEvent("ui-language-change",{detail:{lang}}));
  }
  function init(){
    applyStatic();
    const sel=document.getElementById("uiLanguage");
    if(sel){sel.value=lang;sel.addEventListener("change",()=>setLanguage(sel.value))}
  }
  window.ImageMlxI18n={ui,setLanguage,getLanguage:()=>lang,applyStatic,EN};
  init();
})();