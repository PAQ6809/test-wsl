from __future__ import annotations
import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any, Callable
import cv2
import numpy as np

IMAGE_EXTS={".jpg",".jpeg",".png",".webp",".bmp",".tif",".tiff"}
VIDEO_EXTS={".mp4",".mov",".mkv",".webm",".avi",".m4v",".mts",".m2ts"}

class Cancelled(RuntimeError): pass

def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda:fh.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()

def ffprobe(path: Path)->dict[str,Any]:
    p=subprocess.run(["ffprobe","-v","error","-show_format","-show_streams","-of","json",str(path)],capture_output=True,text=True,check=True)
    return json.loads(p.stdout)

def duration(meta:dict[str,Any])->float:
    try:return float(meta.get("format",{}).get("duration") or 0)
    except:return 0.0

def dimensions(meta:dict[str,Any])->tuple[int,int]:
    v=next((s for s in meta.get("streams",[]) if s.get("codec_type")=="video"),{})
    return int(v.get("width") or 0),int(v.get("height") or 0)

def estimate_image(img:np.ndarray)->dict[str,float]:
    gray=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
    return {"sharpness_laplacian":round(float(cv2.Laplacian(gray,cv2.CV_64F).var()),3),"noise_estimate":round(float(np.median(np.abs(gray.astype(np.float32)-cv2.GaussianBlur(gray,(3,3),0)))),3)}

def image_restore(src:Path,out:Path,job:dict[str,Any])->dict[str,Any]:
    img=cv2.imread(str(src),cv2.IMREAD_COLOR)
    if img is None:raise RuntimeError("無法解碼圖片")
    if img.shape[0]*img.shape[1]>250_000_000:raise RuntimeError("圖片像素超過安全上限")
    before=estimate_image(img);preset=job.get("preset","balanced")
    if preset=="light":restored=cv2.bilateralFilter(img,5,18,18)
    elif preset=="strong":restored=cv2.fastNlMeansDenoisingColored(img,None,7,7,7,21);restored=cv2.bilateralFilter(restored,7,28,28)
    else:restored=cv2.fastNlMeansDenoisingColored(img,None,4,4,7,21);restored=cv2.bilateralFilter(restored,5,20,20)
    h,w=restored.shape[:2];target=max(h,int(job.get("target_height",1080)))
    if target>h:restored=cv2.resize(restored,(int(round(w*target/h/2)*2),target),interpolation=cv2.INTER_LANCZOS4)
    blur=cv2.GaussianBlur(restored,(0,0),1.2);amount={"light":.30,"balanced":.45,"strong":.58}.get(preset,.45);restored=cv2.addWeighted(restored,1+amount,blur,-amount,0)
    out.parent.mkdir(parents=True,exist_ok=True);temp=out.with_name(out.stem+".part"+out.suffix)
    params=[cv2.IMWRITE_JPEG_QUALITY,96] if out.suffix.lower() in {".jpg",".jpeg"} else []
    if not cv2.imwrite(str(temp),restored,params):raise RuntimeError("圖片輸出失敗")
    temp.replace(out)
    return {"media_type":"image","input_dimensions":[w,h],"output_dimensions":[restored.shape[1],restored.shape[0]],"quality_before":before,"quality_after":estimate_image(restored),"truth_note":"改善壓縮瑕疵與觀看清晰度；未宣稱找回被刪除或刻意遮蔽的原始像素。"}

def filters(job:dict[str,Any],meta:dict[str,Any])->str:
    preset=job.get("preset","balanced");opts=job.get("options") or {};v=next((s for s in meta.get("streams",[]) if s.get("codec_type")=="video"),{});fs=[]
    if opts.get("deinterlace",True) and str(v.get("field_order","progressive")) not in {"progressive","unknown",""}:fs.append("bwdif=mode=send_frame:parity=auto:deint=all")
    if opts.get("deblock",True):fs.append({"light":"deblock=filter=weak:block=8:alpha=0.07:beta=0.035:gamma=0.04:delta=0.04","balanced":"deblock=filter=weak:block=8:alpha=0.09:beta=0.045:gamma=0.05:delta=0.05","strong":"deblock=filter=strong:block=8:alpha=0.11:beta=0.065:gamma=0.055:delta=0.055"}[preset])
    if opts.get("denoise",True):fs.append({"light":"hqdn3d=0.8:0.8:2.5:2.5","balanced":"hqdn3d=1.3:1.2:4.2:4.0","strong":"hqdn3d=2.2:2.0:6.0:5.0"}[preset])
    if opts.get("deband",True):
        t={"light":"0.012","balanced":"0.016","strong":"0.022"}[preset];fs.append(f"deband=1thr={t}:2thr={t}:3thr={t}:range=16:blur=1:coupling=1")
    if opts.get("sharpen",True):fs.append(f"unsharp=5:5:{ {'light':'.22','balanced':'.36','strong':'.50'}[preset] }:5:5:0.0")
    src_h=int(v.get("height") or 0);target=max(src_h,int(job.get("target_height",1080)))
    if target>src_h:fs.append(f"scale=-2:{target}:flags=lanczos")
    fs.append("format=yuv420p")
    return ",".join(fs)

def plan(total:float,seconds:int=300)->list[dict[str,float|int]]:
    if total<=0:return [{"segment_index":0,"start_seconds":0.0,"duration_seconds":0.0}]
    return [{"segment_index":i,"start_seconds":i*seconds,"duration_seconds":min(seconds,max(.001,total-i*seconds))} for i in range(max(1,math.ceil(total/seconds)))]

def run_progress(cmd:list[str],expected:float,on_progress:Callable[[float],None],check_cancel:Callable[[],None])->None:
    proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1);tail=[];last=0.0
    assert proc.stdout
    try:
        for raw in proc.stdout:
            check_cancel();line=raw.strip();tail.append(line);tail=tail[-80:]
            if line.startswith("out_time_us=") and expected>0:
                try:
                    p=min(1.0,int(line.split("=",1)[1])/1_000_000/expected)
                    if p-last>.01:on_progress(p);last=p
                except:pass
        rc=proc.wait()
        if rc:raise RuntimeError("FFmpeg失敗："+"\n".join(tail[-25:]))
    except Exception:
        if proc.poll() is None:
            proc.terminate()
            try:proc.wait(8)
            except subprocess.TimeoutExpired:proc.kill()
        raise

def video_restore(src:Path,out:Path,job:dict[str,Any],work:Path,segment_seconds:int,on_segment:Callable[[dict[str,Any]],None],heartbeat:Callable[[str,float],None],check_cancel:Callable[[],None])->dict[str,Any]:
    meta=ffprobe(src);total=duration(meta)
    if total<=0:raise RuntimeError("無法取得影片長度")
    if total>12*3600:raise RuntimeError("影片超過12小時安全上限")
    segs=plan(total,segment_seconds);segdir=work/"segments";segdir.mkdir(parents=True,exist_ok=True);filtergraph=filters(job,meta)
    for i,seg in enumerate(segs):
        check_cancel();idx=int(seg["segment_index"]);target=segdir/f"segment-{idx:05d}.mp4"
        if target.exists():
            try:
                if duration(ffprobe(target))>0:on_segment({**seg,"status":"completed","attempts":0,"checkpoint_path":str(target),"checksum":sha256_file(target),"progress":70+25*(i+1)/len(segs),"stage":f"沿用檢查點 {i+1} / {len(segs)}"});continue
            except:target.unlink(missing_ok=True)
        temp=target.with_suffix(".part.mp4");temp.unlink(missing_ok=True)
        cmd=["ffmpeg","-y","-v","error","-ss",f"{float(seg['start_seconds']):.6f}","-i",str(src),"-t",f"{float(seg['duration_seconds']):.6f}","-map","0:v:0","-map","0:a?","-vf",filtergraph,"-c:v","libx264","-preset","medium","-crf",str((job.get("options")or{}).get("crf",16)),"-c:a","aac","-b:a","192k","-movflags","+faststart","-progress","pipe:1","-nostats",str(temp)]
        on_segment({**seg,"status":"processing","attempts":1,"progress":70+25*i/len(segs),"stage":f"修復第 {i+1} / {len(segs)} 段"})
        run_progress(cmd,float(seg["duration_seconds"]),lambda p:heartbeat(f"修復第 {i+1} / {len(segs)} 段",70+25*(i+p)/len(segs)),check_cancel)
        temp.replace(target);on_segment({**seg,"status":"completed","attempts":1,"checkpoint_path":str(target),"checksum":sha256_file(target),"progress":70+25*(i+1)/len(segs),"stage":f"已完成第 {i+1} / {len(segs)} 段"})
    concat=work/"concat.txt";concat.write_text("\n".join(f"file '{p.as_posix()}'" for p in sorted(segdir.glob('segment-*.mp4'))),encoding="utf-8")
    tempout=out.with_suffix(".part.mp4");subprocess.run(["ffmpeg","-y","-v","error","-f","concat","-safe","0","-i",str(concat),"-c","copy","-movflags","+faststart",str(tempout)],check=True);tempout.replace(out)
    result=ffprobe(out);ow,oh=dimensions(result);iw,ih=dimensions(meta);od=duration(result)
    if oh<max(ih,int(job.get("target_height",1080))):raise RuntimeError("輸出解析度低於目標")
    if abs(od-total)>max(2.0,total*.003):raise RuntimeError(f"輸出長度驗證失敗：來源{total:.3f}s，輸出{od:.3f}s")
    return {"media_type":"video","input_dimensions":[iw,ih],"output_dimensions":[ow,oh],"input_duration":total,"output_duration":od,"segments":len(segs),"filters":filtergraph,"truth_note":"輸出保留來源時間軸並改善壓縮、雜訊與解析度；AI或超解析生成的微細節不可視為原始事實。"}
