from __future__ import annotations
import hashlib
import json
import os
import platform
import shutil
import signal
import sys
import time
from pathlib import Path
from typing import Any
from . import __version__
from .api import WorkerAPI
from .config import settings
from .media import IMAGE_EXTS, VIDEO_EXTS, Cancelled, image_restore, sha256_file, video_restore
from .state import AtomicState

STOP=False
def stop(*_:Any)->None:
    global STOP;STOP=True

def split_file(path:Path,size:int):
    with path.open('rb') as fh:
        part=1
        while True:
            data=fh.read(size)
            if not data:break
            yield part,data;part+=1

def upload_blob(api:WorkerAPI,job:dict[str,Any],kind:str,part_number:int,name:str,data:bytes,content_type:str)->dict[str,Any]:
    work=settings.data_dir/job['id']/"upload";work.mkdir(parents=True,exist_ok=True);tmp=work/name;tmp.write_bytes(data);digest=hashlib.sha256(data).hexdigest();signed=api.call('create_output_upload',job_id=job['id'],kind=kind,part_number=part_number,filename=name);api.upload_signed(signed['signed_url'],signed['token'],tmp,content_type);api.call('register_output',job_id=job['id'],kind=kind,part_number=part_number,object_path=signed['path'],size=len(data),sha256=digest,filename=name);tmp.unlink(missing_ok=True);return signed

def receive_source(api:WorkerAPI,job:dict[str,Any],root:Path,state_store:AtomicState)->Path:
    state=state_store.load();source=root/'source'/str(job.get('safe_name') or job['filename']);source.parent.mkdir(parents=True,exist_ok=True)
    expected=int(state.get('source_bytes',0))
    if source.exists() and source.stat().st_size!=expected:
        with source.open('r+b') as fh:fh.truncate(expected)
    elif not source.exists():source.touch()
    last=int(state.get('last_part',0))
    while not STOP:
        status=api.call('status',job_id=job['id'])['job']
        if status.get('cancel_requested'):raise Cancelled()
        result=api.call('parts',job_id=job['id'],after=last);parts=result.get('parts',[])
        if not parts:
            if result.get('upload_complete') and last>=int(result.get('total_parts') or 0):break
            api.call('heartbeat',job_id=job['id'],status='uploading',stage=f"等待來源分段；已接收 {last} / {result.get('total_parts')}",progress=min(70,last/max(1,int(result.get('total_parts')or 1))*70));time.sleep(settings.poll_seconds);continue
        for part in parts:
            num=int(part['part_number'])
            if num<=last:api.call('consume_part',job_id=job['id'],part_number=num);continue
            if num!=last+1:break
            signed=api.call('signed_download',job_id=job['id'],part_number=num);tmp=root/'incoming'/f"{num:06d}.part";api.download(signed['url'],tmp)
            if tmp.stat().st_size!=int(part['size']):raise RuntimeError(f"來源分段{num}大小不符")
            if sha256_file(tmp)!=part['sha256']:raise RuntimeError(f"來源分段{num} SHA-256不符")
            with source.open('ab') as out,tmp.open('rb') as inp:
                shutil.copyfileobj(inp,out,1024*1024);out.flush();os.fsync(out.fileno())
            last=num;expected+=tmp.stat().st_size;state.update(last_part=last,source_bytes=expected);state_store.save(state);api.call('consume_part',job_id=job['id'],part_number=num);tmp.unlink(missing_ok=True)
    if STOP:raise Cancelled()
    if source.stat().st_size!=int(job['file_size']):raise RuntimeError(f"完整來源大小不符：{source.stat().st_size} != {job['file_size']}")
    api.call('source_ready',job_id=job['id']);return source

def process_job(api:WorkerAPI,job:dict[str,Any])->None:
    root=settings.data_dir/job['id'];root.mkdir(parents=True,exist_ok=True);state=AtomicState(root/'state.json')
    try:
        source=receive_source(api,job,root,state);suffix=Path(job['filename']).suffix.lower();outdir=root/'output';outdir.mkdir(exist_ok=True)
        if suffix in IMAGE_EXTS:
            output=outdir/f"restored-{Path(job['safe_name']).stem}.jpg";api.call('heartbeat',job_id=job['id'],status='processing',stage='修復圖片',progress=75);meta=image_restore(source,output,job)
        elif suffix in VIDEO_EXTS:
            output=outdir/f"restored-{Path(job['safe_name']).stem}.mp4"
            def cancelled():
                if STOP:raise Cancelled()
                status=api.call('status',job_id=job['id'])['job']
                if status.get('cancel_requested'):raise Cancelled()
            def heartbeat(stage:str,progress:float):api.call('heartbeat',job_id=job['id'],status='processing',stage=stage,progress=progress)
            def segment(seg:dict[str,Any]):api.call('segment_upsert',job_id=job['id'],**seg)
            meta=video_restore(source,output,job,root,settings.segment_seconds,segment,heartbeat,cancelled)
        else:raise RuntimeError(f"不支援的副檔名：{suffix}")
        api.call('heartbeat',job_id=job['id'],status='processing',stage='驗證成品並產生可信度報告',progress=96)
        report={"schema_version":"1.0","job_id":job['id'],"generated_at":time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),"worker":{"id":settings.worker_id,"version":__version__,"platform":platform.platform()},"input":{"filename":job['filename'],"size":job['file_size'],"sha256":sha256_file(source)},"output":{"filename":output.name,"size":output.stat().st_size,"sha256":sha256_file(output)},"restoration":meta,"disclaimer":"本報告不證明生成式細節等同原始內容；完整馬賽克、塗黑或已刪除資訊無法被驗證性還原。"}
        report_bytes=json.dumps(report,ensure_ascii=False,indent=2).encode();report_signed=upload_blob(api,job,'report',0,'truth-report.json',report_bytes,'application/json')
        total_parts=0
        for number,data in split_file(output,settings.output_part_bytes):
            upload_blob(api,job,'download',number,f"{number:06d}.part",data,'application/octet-stream');total_parts=number;api.call('heartbeat',job_id=job['id'],status='processing',stage=f"上傳成品分段 {number}",progress=min(99,97+number/max(1,(output.stat().st_size+settings.output_part_bytes-1)//settings.output_part_bytes)*2))
        api.call('complete',job_id=job['id'],output_filename=output.name,output_mime='image/jpeg' if suffix in IMAGE_EXTS else 'video/mp4',result_metadata={**meta,"output_parts":total_parts,"report_path":report_signed['path']})
    except Cancelled:api.call('cancelled',job_id=job['id'])
    except Exception as exc:
        api.call('fail',job_id=job['id'],error=str(exc),retry=True);raise

def capabilities()->dict[str,Any]:
    return {"platform":platform.platform(),"python":platform.python_version(),"ffmpeg":bool(shutil.which('ffmpeg')),"ffprobe":bool(shutil.which('ffprobe')),"video_ai":bool(os.getenv('VIDEO_AI_COMMAND')),"image_ai":bool(os.getenv('IMAGE_AI_COMMAND'))}

def cleanup()->None:
    cutoff=time.time()-settings.keep_days*86400
    if not settings.data_dir.exists():return
    for path in settings.data_dir.iterdir():
        try:
            if path.is_dir() and path.stat().st_mtime<cutoff:shutil.rmtree(path)
        except OSError:pass

def run()->None:
    settings.validate();settings.data_dir.mkdir(parents=True,exist_ok=True);api=WorkerAPI();api.call('register',name=settings.worker_name,capabilities=capabilities(),version=__version__);print(f"Restoration Worker {__version__} 已連線：{settings.worker_name}")
    while not STOP:
        try:
            cleanup();claimed=api.call('claim').get('job')
            if not claimed:api.call('heartbeat',status='idle');time.sleep(settings.poll_seconds);continue
            print(f"接手工作 {claimed['id']}：{claimed['filename']}");process_job(api,claimed)
        except KeyboardInterrupt:break
        except Exception as exc:print(f"Worker錯誤：{exc}",file=sys.stderr);time.sleep(min(30,settings.poll_seconds*2))

def main()->None:
    signal.signal(signal.SIGINT,stop);signal.signal(signal.SIGTERM,stop);run()
if __name__=='__main__':main()
