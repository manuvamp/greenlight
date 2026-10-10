import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={'width':1440,'height':810}, device_scale_factor=4/3)
        pg = await ctx.new_page()
        await pg.goto('http://127.0.0.1:8080/replay/kubedeployer-pydantic-v2?speed=instant'); await pg.wait_for_timeout(2500)
        await pg.screenshot(path='v1440.png')
        info = await pg.evaluate("""()=>[...document.querySelectorAll('section.panel')].map(e=>[e.className,Math.round(e.getBoundingClientRect().x),Math.round(e.getBoundingClientRect().y+scrollY),Math.round(e.getBoundingClientRect().width),Math.round(e.getBoundingClientRect().height)])""")
        for i in info: print(i)
        await b.close()
asyncio.run(main())
