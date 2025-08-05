import asyncio
from playwright.async_api import async_playwright

async def scrape_railyatri_buses(source, destination, travel_date):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto("https://www.railyatri.in/bus-booking", timeout=30000)

        # Type source and select first suggestion
        await page.click("input[placeholder='Source City']")
        await page.fill("input[placeholder='Source City']", source)
        await page.wait_for_selector("li.AutoInput_suggestion__Gri5M", timeout=5000)
        await page.click("li.AutoInput_suggestion__Gri5M")  # First matching city
        await asyncio.sleep(1)

        # Type destination and select first suggestion
        await page.click("input[placeholder='Destination City']")
        await page.fill("input[placeholder='Destination City']", destination)
        await page.wait_for_selector("li.AutoInput_suggestion__Gri5M", timeout=5000)
        await page.click("li.AutoInput_suggestion__Gri5M")
        await asyncio.sleep(1)

        # Set travel date

        await page.wait_for_selector("div.RySearchFormWrapper_futureDateItem__XrrvO", timeout=5000)

        await page.locator("div.RySearchFormWrapper_futureDateItem__XrrvO span", has_text=travel_date[:2]).first.click()
        await asyncio.sleep(1)


        # Click Search Buses
        await page.click("button:has-text('Search')")
        # await page.wait_for_selector("div.bus-item", timeout=20000)

        # Extract buses
        buses = page.locator("div.BusListItem_item__A06dZ")
        count = await buses.count()
        print(f"🔍 Found {count} buses")

        results = []

        for i in range(count):
            try:
                bus = buses.nth(i)
                await bus.scroll_into_view_if_needed()

                brand = await bus.locator("img").first.get_attribute("alt")
                times = await bus.locator(".BusListItem_timeStart__hdBJc").all_inner_texts()
                boarding = await bus.locator(".BusListItem_boardingPoint__9ZDFi").all_inner_texts()
                duration = await bus.locator(".BusListItem_totaldifferTime__QJzje").inner_text()
                seats_data = await bus.locator(".BusListItem_seatContainer__4nMm8").all_inner_texts()
                rating = await bus.locator(".route_goodRating__OoPIL").inner_text()
                amenities = await bus.locator(".BusListItem_tagStyle__9vsgb").inner_text()
                seats_left = await bus.locator(".BusListItem_rightBottomBlock__bUXT2").inner_text()

                seat_info = []
                for s in range(await bus.locator(".BusListItem_seatContainer__4nMm8").count()):
                    seat_type = await bus.locator(".BusListItem_seatName__NqoHl").nth(s).inner_text()
                    price = await bus.locator(".BusListItem_mainPrice__kA_k3").nth(s).inner_text()
                    seat_info.append({"type": seat_type, "price": price})

                results.append({
                    "brand": brand,
                    "start_time": times[0],
                    "end_time": times[1] if len(times) > 1 else "",
                    "pickup": boarding[0] if boarding else "",
                    "drop": boarding[1] if len(boarding) > 1 else "",
                    "duration": duration,
                    "seats": seat_info,
                    "rating": rating,
                    "amenities": amenities,
                    "seats_left": seats_left
                })
                print("pickup",boarding)

                print(f"✅ Scraped: {brand} - ₹{seat_info[0]['price']}")
            except Exception as e:
                print(f"⚠️ Error scraping bus {i+1}: {e}")

        await browser.close()
        return results

# Example usage
if __name__ == "__main__":
    from datetime import datetime

    asyncio.run(scrape_railyatri_buses("delhi","dehradun","30-07-2025"))