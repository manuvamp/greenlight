import asyncio
from rec import *
DUR=292.063
async def at(r, s):
    d = s-(time.perf_counter()-r.t0)
    if d>0: await asyncio.sleep(d)
async def smooth_scroll(pg, y, ms=1200):
    await pg.evaluate("(([y,ms])=>{const s=scrollY,t0=performance.now();const f=n=>{const k=Math.min(1,(n-t0)/ms);const e=k<.5?2*k*k:1-Math.pow(-2*k+2,2)/2;scrollTo({top:s+(y-s)*e,behavior:'instant'});if(k<1)requestAnimationFrame(f)};requestAnimationFrame(f)})(arguments[0])" if False else "([y,ms])=>{const s=scrollY,t0=performance.now();const f=n=>{const k=Math.min(1,(n-t0)/ms);const e=k<.5?2*k*k:1-Math.pow(-2*k+2,2)/2;scrollTo({top:s+(y-s)*e,behavior:'instant'});if(k<1)requestAnimationFrame(f)};requestAnimationFrame(f)}", [y,ms])
async def main():
    async with async_playwright() as p:
        b,ctx,pg=await newpage(p)
        await pg.goto(BASE+'/replay/kubedeployer-pydantic-v2?speed=1'); await pg.wait_for_timeout(1500)
        await pause(pg); await seek(pg,10.8,DUR); await pg.wait_for_timeout(600)
        await pg.mouse.move(700,5)
        r=Rec(pg,ctx); await r.start()
        # B1 baseline 0-8
        await at(r,0.8); await play(pg)
        await at(r,4.9); await pause(pg)          # t ~ 14.9
        # B2 bump 8-15
        await at(r,8.0); await play(pg)
        await at(r,10.4); await pause(pg)         # t ~ 17.3 then continue
        await play(pg)
        await at(r,11.0); await pause(pg)         # t ~ 17.9
        # B3 research dwell 15-24 (paused)
        # B4 plan 24-33: resume 1x, scroll to plan
        await at(r,24.0); await play(pg); await smooth_scroll(pg,400,1800)
        await at(r,33.0); await speed(pg,'4×')
        # B5 migrate 33-43 at 4x, then 16x for repair feel
        await at(r,40.5); await speed(pg,'16×')
        await at(r,43.0)
        await r.stop('s3a.mp4')
        await b.close()
        # B6 climb: separate take
        b,ctx,pg=await newpage(p)
        await pg.goto(BASE+'/replay/kubedeployer-pydantic-v2?speed=8'); await pg.wait_for_timeout(1500)
        await pause(pg); await seek(pg,238,DUR); await pg.evaluate("scrollTo({top:60,behavior:'instant'})"); await pg.wait_for_timeout(500)
        r=Rec(pg,ctx); await r.start()
        await at(r,0.3); await play(pg)
        await at(r,5.8); await pause(pg)
        await at(r,7.0); await seek(pg,DUR-0.3,DUR); await pg.evaluate("scrollTo({top:60,behavior:'instant'})")
        await at(r,12.5)
        await r.stop('s3b.mp4')
        await b.close()
asyncio.run(main())
