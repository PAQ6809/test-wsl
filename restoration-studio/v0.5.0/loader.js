(async()=>{"use strict";
const status=document.getElementById("boot-status"),setStatus=t=>{if(status)status.textContent=t};
const RELEASE_BASE="https://raw.githubusercontent.com/PAQ6809/test-wsl/bf71708a459c41c4b24a7c91da342e4506d9ea9f/restoration-studio/v0.5.0";
const fetchText=async p=>{const r=await fetch(`${RELEASE_BASE}${p}`,{cache:"no-store"});if(!r.ok)throw new Error(`載入失敗：${p}`);return r.text()};
const join=async list=>(await Promise.all(list.map(fetchText))).join("");
const write=(html,css)=>{html=html.replace(/<link rel="stylesheet" href="\/styles\.css">/,`<style>${css}</style>`).replace(/<script src="https:\/\/cdn\.jsdelivr\.net\/npm\/@supabase\/supabase-js@2\.57\.4\/dist\/umd\/supabase\.min\.js"><\/script>/,"").replace(/<script src="\/config\.js"><\/script>/,"").replace(/<script src="\/app\.js" defer><\/script>/,"");document.open();document.write(html);document.close()};
try{
 setStatus("載入版本清單");const m=await fetch(`${RELEASE_BASE}/source-manifest.json`,{cache:"no-store"}).then(r=>{if(!r.ok)throw new Error("發行清單不存在");return r.json()});
 const css=await join(m.styles),path=location.pathname,legal={"/privacy":"privacy","/privacy.html":"privacy","/terms":"terms","/terms.html":"terms","/security":"security","/security.html":"security","/help":"help","/help.html":"help"}[path];
 if(legal){write(await join(m[legal]),css);return}
 setStatus("載入工作台");const [html,app,imageWorker]=await Promise.all([join(m.main),join(m.app),join(m.imageWorker)]);write(html,css);
 window.RESTORATION_CONFIG=Object.freeze({version:"0.5.0",supabaseUrl:"https://goedzzhhvvnfczgnkqlv.supabase.co",supabaseKey:"sb_publishable_6whjqbImNMa7BR9i-96M-w_dFIOFeMN",storageBucket:"restoration-media",localWorkerUrl:"http://127.0.0.1:8787",workerApiUrl:"https://goedzzhhvvnfczgnkqlv.supabase.co/functions/v1/restoration-worker-api",relayChunkBytes:6291456,relayBufferBytes:402653184,maxBrowserImagePixels:32000000,disclaimerVersion:"2026-07-13"});
 window.RESTORATION_IMAGE_WORKER_URL=URL.createObjectURL(new Blob([imageWorker],{type:"text/javascript"}));
 const workerLink=document.querySelector('a[href="/downloads/restoration-worker-v0.5.0.zip"]');if(workerLink){workerLink.href="https://github.com/PAQ6809/test-wsl/tree/bf71708a459c41c4b24a7c91da342e4506d9ea9f/restoration-studio/v0.5.0/worker";workerLink.target="_blank";workerLink.rel="noopener noreferrer";workerLink.textContent="開啟 Personal Worker 原始碼"}
 const sdk=document.createElement("script");sdk.src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.57.4/dist/umd/supabase.min.js";sdk.onload=async()=>{const patched=app.replace('new Worker("/image-worker.js")','new Worker(window.RESTORATION_IMAGE_WORKER_URL)');const u=URL.createObjectURL(new Blob([patched],{type:"text/javascript"}));try{await import(u)}finally{setTimeout(()=>URL.revokeObjectURL(u),5000)}};sdk.onerror=()=>{throw new Error("Supabase SDK載入失敗")};document.head.appendChild(sdk);
 if("serviceWorker" in navigator)navigator.serviceWorker.register("/sw.js").catch(console.warn);
}catch(e){console.error(e);document.body.innerHTML=`<main style="min-height:100vh;display:grid;place-items:center;background:#080b10;color:#edf4f9;font:16px system-ui;text-align:center;padding:24px"><div><h1>工作台載入失敗</h1><p style="color:#ffb8c1">${String(e.message||e)}</p><button onclick="location.reload()" style="padding:12px 18px">重新載入</button></div></main>`}
})();
