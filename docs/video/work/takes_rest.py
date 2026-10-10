import asyncio, sys
from rec import *
DUR=292.063
async def at(r, s):
    d = s-(time.perf_counter()-r.t0)
    if d>0: await asyncio.sleep(d)
SCROLL="""([y,ms])=>{const s=scrollY,t0=performance.now();const f=n=>{const k=Math.min(1,(n-t0)/ms);const e=k<.5?2*k*k:1-Math.pow(-2*k+2,2)/2;scrollTo({top:s+(y-s)*e,behavior:'instant'});if(k<1)requestAnimationFrame(f)};requestAnimationFrame(f)}"""
async def s4(p):
    b,ctx,pg=await newpage(p)
    await pg.goto(BASE+'/replay/kubedeployer-pydantic-v2?speed=instant'); await pg.wait_for_timeout(2000)
    Y=await pg.evaluate("document.querySelector('.verify-panel').getBoundingClientRect().top+scrollY")
    print('verify Y',Y)
    await seek(pg,287.9,DUR); await speed(pg,'1×'); await pause(pg)
    await pg.evaluate(f"scrollTo({{top:{Y-100},behavior:'instant'}})"); await pg.wait_for_timeout(500)
    r=Rec(pg,ctx); await r.start()
    await at(r,2.0); await play(pg)
    await at(r,24.0); await r.stop('s4.mp4'); await b.close()
async def s5(p):
    b,ctx,pg=await newpage(p)
    await pg.goto(BASE+'/replay/kubedeployer-pydantic-v2?speed=16'); await pg.wait_for_timeout(1200)
    await pause(pg); await seek(pg,0,DUR); await pg.evaluate("scrollTo({top:150,behavior:'instant'})"); await pg.wait_for_timeout(500)
    r=Rec(pg,ctx); await r.start()
    await at(r,1.0); await play(pg)
    await at(r,26.0); await r.stop('s5.mp4'); await b.close()
async def s6(p):
    b,ctx,pg=await newpage(p)
    await pg.goto(BASE+'/scoreboard'); await pg.wait_for_timeout(1500)
    r=Rec(pg,ctx); await r.start()
    await at(r,4.0); await pg.evaluate(SCROLL,[300,1500])
    await at(r,8.5)
    hl=await pg.evaluate("""()=>{const out=[];for(const n of ['terka','blocklib']){const a=[...document.querySelectorAll('a,span,div')].find(e=>e.children.length===0&&e.textContent.trim()===n);if(!a){out.push(n+' NOTFOUND');continue}let row=a.closest('tr')||a.parentElement.parentElement.parentElement;row.style.transition='all .4s';row.style.boxShadow='inset 0 0 0 2px #3ddc84, 0 0 40px rgba(61,220,132,.35)';row.style.background='rgba(61,220,132,.10)';out.push(n+' '+row.tagName+' '+Math.round(row.getBoundingClientRect().top))}return out}""")
    print(hl)
    await at(r,20.5); await r.stop('s6.mp4'); await b.close()
async def s7(p):
    b,ctx,pg=await newpage(p)
    await pg.goto(BASE+'/replay/kubedeployer-pydantic-v2?speed=instant'); await pg.wait_for_timeout(2000)
    Y=await pg.evaluate("document.querySelector('.pr-panel').getBoundingClientRect().top+scrollY")
    await pg.evaluate(f"scrollTo({{top:{Y-100},behavior:'instant'}})"); await pg.wait_for_timeout(600)
    r=Rec(pg,ctx); await r.start()
    await at(r,1.5); await pg.evaluate(SCROLL,[Y-100+620,9000])
    await at(r,13.0); await r.stop('s7.mp4'); await b.close()
async def home(p):
    b,ctx,pg=await newpage(p)
    await pg.goto(BASE+'/'); 
    r=Rec(pg,ctx); await r.start()
    await at(r,15.0); await r.stop('home.mp4'); await b.close()
async def stills(p):
    b,ctx,pg=await newpage(p,1440,810,4/3)
    await pg.goto(BASE+'/replay/nsopy-numpy-v2?speed=instant'); await pg.wait_for_timeout(2500)
    await pg.screenshot(path='nsopy.png')
    for rid in ('terka-sqlalchemy-v2','blocklib-pydantic-v2'):
        await pg.goto(BASE+f'/replay/{rid}?speed=instant'); await pg.wait_for_timeout(2500); await pg.screenshot(path=f'{rid}.png')
    await b.close()
async def main():
    async with async_playwright() as p:
        for fn in sys.argv[1:]:
            await globals()[fn](p)
asyncio.run(main())
