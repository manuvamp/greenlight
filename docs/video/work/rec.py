import asyncio, base64, os, subprocess, time, shutil, json
from playwright.async_api import async_playwright

BASE='http://127.0.0.1:8080'
W,H=1440,810
DSF=4/3

class Rec:
    def __init__(self, page, ctx):
        self.page=page; self.ctx=ctx; self.frames=[]; self.cdp=None; self.t0=None
    async def start(self):
        self.cdp=await self.ctx.new_cdp_session(self.page)
        async def on_frame(p):
            self.frames.append((time.perf_counter(), p['data']))
            try: await self.cdp.send('Page.screencastFrameAck',{'sessionId':p['sessionId']})
            except Exception: pass
        self.cdp.on('Page.screencastFrame', lambda p: asyncio.ensure_future(on_frame(p)))
        await self.cdp.send('Page.startScreencast',{'format':'jpeg','quality':92,'maxWidth':1920,'maxHeight':1080,'everyNthFrame':1})
        self.t0=time.perf_counter()
    async def stop(self, out, fps=30):
        t1=time.perf_counter()
        await self.cdp.send('Page.stopScreencast')
        d=f'frames_{os.path.basename(out)}'
        shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
        fr=self.frames
        lines=[]
        # make first frame start at t0
        for i,(t,data) in enumerate(fr):
            fn=f'{d}/f{i:05d}.jpg'
            open(fn,'wb').write(base64.b64decode(data))
            tn = fr[i+1][0] if i+1<len(fr) else t1
            dur = max(0.001, tn-(t if i>0 else self.t0 if t>self.t0 else t))
            lines.append(f"file '{fn}'\nduration {dur:.4f}")
        lines.append(f"file '{d}/f{len(fr)-1:05d}.jpg'")
        open(f'{d}.txt','w').write('\n'.join(lines))
        subprocess.run(['ffmpeg','-y','-loglevel','error','-f','concat','-safe','0','-i',f'{d}.txt','-vf',f'fps={fps},scale=1920:1080:flags=lanczos,format=yuv420p','-c:v','libx264','-crf','14','-preset','medium','-g','30','-movflags','+faststart',out],check=True)
        n=len(fr); shutil.rmtree(d, ignore_errors=True); os.remove(f'{d}.txt')
        print(out,'frames',n,'secs',round(t1-self.t0,2),'avg fps',round(n/(t1-self.t0),1))

async def newpage(p, w=W,h=H,dsf=DSF):
    b=await p.chromium.launch()
    ctx=await b.new_context(viewport={'width':w,'height':h}, device_scale_factor=dsf)
    pg=await ctx.new_page()
    return b,ctx,pg

async def seek(pg, t, dur):
    for attempt in range(4):
        await pg.evaluate("scrollTo({top:0,behavior:'instant'})"); await pg.wait_for_timeout(150)
        box=await pg.evaluate("(()=>{const r=document.querySelector('.scrub').getBoundingClientRect();return [r.left,r.width,r.top+r.height/2]})()")
        x=box[0]+min(box[1]-3,box[1]*t/dur)
        await pg.mouse.move(x-5, box[2]); await pg.mouse.click(x, box[2])
        await pg.wait_for_timeout(100)
        v=float(await pg.evaluate("document.querySelector('.scrub').getAttribute('aria-valuenow')"))
        print('seek',t,'->',v,'attempt',attempt)
        if abs(v-t)<2.5: return
async def pause_state(pg):
    return await pg.evaluate("document.querySelector('.pb-main').getAttribute('aria-label')")
async def pause(pg):
    if await pause_state(pg)=='Pause': await pg.evaluate("document.querySelector('.pb-main').click()")
async def play(pg):
    if await pause_state(pg)!='Pause': await pg.evaluate("document.querySelector('.pb-main').click()")
async def speed(pg, label):
    await pg.evaluate("l=>[...document.querySelectorAll('.seg-btn')].find(b=>b.textContent.trim()===l).click()", label)
async def seek_top(pg,t,dur):
    await pg.evaluate("scrollTo(0,0)"); await pg.wait_for_timeout(50); await seek(pg,t,dur)
