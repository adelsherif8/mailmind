import asyncio
from playwright.async_api import async_playwright
URL = "http://localhost:8095/"
OUT = "/Users/adel/Desktop/GHAI/mailmind/docs/video"


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 1200, "height": 800},
                                  record_video_dir=OUT,
                                  record_video_size={"width": 1200, "height": 800},
                                  device_scale_factor=2)
        page = await ctx.new_page()
        try:
            await page.goto(URL); await page.wait_for_timeout(1800)
            # open the angry refund email (high priority complaint)
            await page.click("#row-m1"); await page.wait_for_timeout(2600)
            # open the outage email
            await page.click("#row-m5"); await page.wait_for_timeout(2400)
            # a scheduling request, then switch tone to friendly (live regen)
            await page.click("#row-m6"); await page.wait_for_timeout(1800)
            await page.click("text=friendly"); await page.wait_for_timeout(7000)
            # approve -> creates draft
            await page.click("text=Approve & create draft"); await page.wait_for_timeout(2600)
        finally:
            await ctx.close(); await b.close()
        print("recorded")

asyncio.run(main())
