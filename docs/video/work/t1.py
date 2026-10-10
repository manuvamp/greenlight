import asyncio
from rec import *
async def main():
    async with async_playwright() as p:
        b,ctx,pg=await newpage(p)
        await pg.goto(BASE+'/replay/kubedeployer-pydantic-v2?speed=1'); await pg.wait_for_timeout(1500)
        await pause(pg)
        print(await pg.evaluate("document.querySelector('.playback-time').textContent"))
        r=Rec(pg,ctx); await r.start()
        await pg.wait_for_timeout(2000)
        await pg.click('.seg-btn:has-text("8×")')
        await play(pg)
        await pg.wait_for_timeout(5000)
        await r.stop('t1.mp4')
        print(await pg.evaluate("document.querySelector('.playback-time').textContent"))
        await b.close()
asyncio.run(main())
