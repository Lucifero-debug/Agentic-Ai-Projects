import asyncio
from playwright.async_api import async_playwright

async def scrape_redbus(source,dest,departure_date):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        # Open Redbus
        await page.goto("https://www.redbus.in/")

        # Input source and destination
        await  page.locator("div[role='button']").nth(0)
        await  page.locator("div[role='button']").nth(0).focus()
        await page.keyboard.type(source, delay=200)
        await page.get_by_placeholder("TO").fill("Dehradun")
        await page.keyboard.press("Enter")

        # Select a future date dynamically
        await page.get_by_placeholder("DATE").click()
        await page.locator("div.date___5895e0:not(.disabled___32d97):not(.past___ef820)").nth(1).click()

        await page.get_by_text("Search Buses").click()

        await page.wait_for_selector("div.TravelsDetails")

        # Get bus cards
        buses = await page.locator("div.TravelsDetails").element_handles()
        print(f"🚌 Found {len(buses)} bus links")

        results = []

        for idx, bus in enumerate(buses):
            print(f"🔄 Processing bus {idx+1}/{len(buses)}")

            try:
                # Scroll into view
                await page.evaluate(
                    "(el) => el.scrollIntoView({ behavior: 'smooth', block: 'center' })", bus
                )
                await asyncio.sleep(0.5)

                # Click the bus
                await bus.click()
                await asyncio.sleep(1.5)

                # Wait for popup (Drawer) to appear
                popup = page.locator("div.bus-details")
                await popup.wait_for(timeout=5000)

                # Extract all details
                name = await page.locator("div.bus-name").text_content()
                fare = await page.locator("span.fare-label").text_content()
                amenities = await page.locator("div.amenity-text").all_inner_texts()
                rest_stop = await page.locator("div.rest-stop-info").text_content()
                bus_type = await page.locator("div.bus-type").text_content()
                cancellation = await page.locator("div.cancellation-policy").text_content()
                offers = await page.locator("div.offer-container").all_inner_texts()

                # Boarding/dropping (example: just first few)
                stops = []
                stop_rows = page.locator("div.bpdp-container .bpdp-row")
                for i in range(await stop_rows.count()):
                    row = stop_rows.nth(i)
                    time = await row.locator("div.bpdp-time").text_content()
                    location = await row.locator("div.bpdp-location").text_content()
                    address = await row.locator("div.bpdp-address").text_content()
                    stops.append({
                        "time": time.strip(),
                        "location": location.strip(),
                        "address": address.strip()
                    })

                results.append({
                    "Name": name.strip(),
                    "Fare": fare.strip(),
                    "Amenities": amenities,
                    "RestStop": rest_stop.strip(),
                    "BusType": bus_type.strip(),
                    "Cancellation": cancellation.strip(),
                    "Offers": offers,
                    "Stops": stops,
                })

                print("✅ Details fetched.")

                # Close popup if necessary
                close_btn = page.locator("div.bus-details div.close-button")
                if await close_btn.is_visible():
                    await close_btn.click()

                await asyncio.sleep(1)

            except Exception as e:
                print(f"❌ Failed to click or fetch bus {idx+1}: {e}")
                continue

        print("🎯 Done.")
        print(results)

        await browser.close()

asyncio.run(scrape_redbus())
