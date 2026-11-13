"""Render one video to out/<name>.mp4 (used by the GitHub Actions release workflow).
usage: python scripts/render.py film <main|pre|seq|c_nae|...> <silent|talk>
       python scripts/render.py teaser <v1|v3|v5|r1|r2>
"""
import asyncio,sys,base64,subprocess,time,os,pathlib
import numpy as np
from playwright.async_api import async_playwright
ROOT=pathlib.Path(__file__).resolve().parent.parent;FONTS=ROOT/'fonts';OUT=ROOT/'out';OUT.mkdir(exist_ok=True)
FILM={'main':'film_main_15min','pre':'film_prequel_5min','seq':'film_sequel_5min','c_nae':'char_nae_3min','c_tae':'char_tae_3min','c_mu':'char_mu_3min','c_sim':'char_sim_3min','c_hel':'char_hel_3min','c_wol':'char_wol_3min','c_kim':'char_kim_3min','c_dir':'char_director_3min','c_asm':'char_asm_3min'}
TEASER={'v1':'teaser_1min','v3':'trailer_3min','v5':'trailer_5min','r1':'reel1_15s','r2':'reel2_15s'}
def css(w,h,teaser):
  f=lambda fam,file,wt='normal':f"@font-face{{font-family:'{fam}';font-weight:{wt};src:url('{(FONTS/file).as_uri()}')}}"
  s=f('Black Han Sans','BlackHanSans-Regular.ttf')+f('Gowun Dodum','GowunDodum-Regular.ttf')+f('Nanum Myeongjo','NanumMyeongjo-Bold.ttf',400)+f('Nanum Myeongjo','NanumMyeongjo-Bold.ttf',700)+f('Nanum Myeongjo','NanumMyeongjo-ExtraBold.ttf',800)
  if teaser:s+=f".stage{{position:fixed!important;left:0;top:0;width:{w}px!important;height:{h}px!important;aspect-ratio:auto!important;margin:0!important;border:0!important;z-index:999}}body{{overflow:hidden}}"
  return s
def ffmpeg(fps,raw,total,out,teaser):
  br=min(2400,int(86*8*1000/total)-140)
  args=['ffmpeg','-y','-loglevel','error','-f','image2pipe','-framerate',str(fps),'-c:v','mjpeg','-i','-','-f','s16le','-ar','44100','-ac','1','-i',raw,'-t',str(total)]
  if fps<24:args+=['-r','24']
  args+=['-c:v','libx264','-preset','veryfast','-crf','25','-maxrate',f'{br}k','-bufsize',f'{2*br}k','-pix_fmt','yuv420p','-af','loudnorm=I=-17:TP=-1.5:LRA=11','-c:a','aac','-b:a','160k','-movflags','+faststart',out]
  return subprocess.Popen(args,stdin=subprocess.PIPE)
def voice(id):
  p=subprocess.run(['ffmpeg','-loglevel','error','-i',str(ROOT/'voices'/f'{id}.mp3'),'-f','s16le','-ar','44100','-ac','1','-'],capture_output=True)
  return np.frombuffer(p.stdout,dtype=np.int16).astype(np.float32)/32767
async def run():
  kind=sys.argv[1]
  async with async_playwright() as p:
    b=await p.chromium.launch(args=['--allow-file-access-from-files'])
    if kind=='film':
      K,MODE=sys.argv[2],sys.argv[3];name=FILM[K]+('_dialogue' if MODE=='talk' else '');W,H=1280,720
      pg=await b.new_page(viewport={'width':1280,'height':900})
      await pg.route('**/fonts.googleapis.com/**',lambda r:r.abort())
      await pg.goto((ROOT/'film.html').as_uri());await pg.add_style_tag(content=css(W,H,False))
      await pg.evaluate("Promise.all([document.fonts.load('800 40px \"Nanum Myeongjo\"'),document.fonts.load('700 40px \"Nanum Myeongjo\"'),document.fonts.load('40px \"Gowun Dodum\"')])");await pg.wait_for_timeout(800)
      total=await pg.evaluate(f"(()=>{{setFilm('{K}','{MODE}');return st.film.total}})()")
      n=await pg.evaluate(f"renderAudioChunks('{K}')");raw=bytearray()
      for i in range(0,n,4_000_000):raw+=base64.b64decode(await pg.evaluate(f"pcmChunk({i},4000000)"))
      mus=np.frombuffer(bytes(raw),dtype=np.int16).astype(np.float32)/32767
      if MODE=='talk':
        duck=np.ones_like(mus);vo=np.zeros_like(mus)
        for t,id,who in await pg.evaluate(f"voiceEvents('{K}')"):
          v=voice(id);s=int(t*44100);e=min(len(mus),s+len(v));vo[s:e]+=v[:e-s]*1.15;duck[max(0,s-6000):min(len(mus),e+9000)]=.55
        duck=np.convolve(duck,np.ones(4410)/4410,mode='same');mus=mus*duck+vo;pk=np.abs(mus).max();mus=mus*(.97/pk) if pk>.97 else mus
      fps=24;frame=lambda i:pg.evaluate(f"frameAt('{K}',{i/fps},'{MODE}')")
    else:
      K=sys.argv[2];name=TEASER[K];W,H=(1080,1920) if K.startswith('r') else (1280,720)
      pg=await b.new_page(viewport={'width':W,'height':H})
      await pg.route('**/fonts.googleapis.com/**',lambda r:r.abort())
      await pg.goto((ROOT/'index.html').as_uri());await pg.add_style_tag(content=css(W,H,True))
      await pg.evaluate("Promise.all([document.fonts.load('40px \"Black Han Sans\"'),document.fonts.load('800 40px \"Nanum Myeongjo\"'),document.fonts.load('40px \"Gowun Dodum\"')])");await pg.wait_for_timeout(1500)
      await pg.evaluate(f"renderFrame('{K}',0)");await pg.wait_for_timeout(400)
      total=await pg.evaluate("st.total");a=await pg.evaluate(f"renderAudio('{K}')")
      mus=np.frombuffer(base64.b64decode(a),dtype=np.int16).astype(np.float32)/32767
      fps=8
      async def frame(i):
        await pg.evaluate(f"renderFrame('{K}',{i/fps})");return 'data:image/jpeg;base64,'+base64.b64encode(await pg.screenshot(type='jpeg',quality=90,clip={'x':0,'y':0,'width':W,'height':H})).decode()
    raw=str(OUT/f'{name}.raw');open(raw,'wb').write((np.clip(mus,-1,1)*32767).astype(np.int16).tobytes())
    ff=ffmpeg(fps,raw,total,str(OUT/f'{name}.mp4'),kind=='teaser');N=int(round(total*fps));t0=time.time()
    for i in range(N):
      u=await frame(i);ff.stdin.write(base64.b64decode(u.split(',',1)[1]))
      if i%1200==0:print(name,i,N,round(time.time()-t0),flush=True)
    ff.stdin.close();ff.wait();os.remove(raw);await b.close();print('DONE',name,flush=True)
asyncio.run(run())
