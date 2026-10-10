import asyncio
from rec import *
async def main():
    async with async_playwright() as p:
        b,ctx,pg=await newpage(p)
        await pg.goto(BASE+'/replay/kubedeployer-pydantic-v2?speed=16'); await pg.wait_for_timeout(5000)
        await pg.evaluate("scrollTo({top:400,behavior:'instant'})")
        await pg.wait_for_timeout(1000)
        await pause(pg)
        for t in (238,):
            box=await pg.evaluate("(()=>{const r=document.querySelector('.scrub').getBoundingClientRect();return [r.left,r.width,r.top+r.height/2,scrollY]})()")
            print(box)
            await seek(pg,t,292.063)
            await pg.wait_for_timeout(300)
            print(await pg.evaluate("document.querySelector('.playback-time').textContent"))
            box=await pg.evaluate("(()=>{const r=document.querySelector('.scrub').getBoundingClientRect();return [r.left,r.width,r.top+r.height/2,scrollY]})()")
            print(box)
        await b.close()
asyncio.run(main())
