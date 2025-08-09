import asyncio
from playwright.async_api import async_playwright

async def fetch_internshala_jobs(query, location="Jaipur", page_num=1):
    url = f"https://internshala.com/internships/page-1/#filter"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(storage_state="auth.json")

        page = await context.new_page()
        await page.goto(url)


        try:
            popup_close_btn = page.locator("#close_popup")
            if await popup_close_btn.is_visible(timeout=3000):
                await popup_close_btn.click()
                print("✅ Closed popup ad")
        except Exception as e:
            print(f"ℹ️ No popup or failed to close: {e}")


        await page.wait_for_load_state("networkidle")


        query="x"+query
        category_div = page.locator("div#select_category_chosen")

        input_box = category_div.locator('input.chosen-search-input')
        await input_box.focus()     


        for char in query:
            await input_box.type(char)
            await asyncio.sleep(0.1) 

        await page.wait_for_selector("ul.chosen-results li.active-result", state="visible")
        await input_box.press("Enter")


        location_div = page.locator("div#city_sidebar_chosen")
        await location_div.click()

        location_box = location_div.locator('input.chosen-search-input')
        await location_box.focus()    


        for char in location:
            await location_box.type(char)
            await asyncio.sleep(0.1) 

        await location_box.press("Enter")
        await page.wait_for_selector("div.individual_internship", timeout=7000)

        job_cards = page.locator("div.individual_internship")
        count = await job_cards.count()
        print(f"\n✅ Found {count} jobs\n")

        job_list=[]

        for i in range(10):
            card = job_cards.nth(i)
            try:
                title = await card.locator("div.company a#job_title").text_content()
                link = await card.locator("div.company a#job_title").get_attribute("href")
                full_link = f"https://internshala.com{link}" if link else None
                
                title_el = card.locator("a#job_title")
                async with context.expect_page() as new_page_info:
                    await title_el.click(force=True)

                new_page = await new_page_info.value
                await new_page.wait_for_load_state("load")

                await new_page.wait_for_selector("div#details_container div.internship_details div.text-container", timeout=5000)

                desc_section = new_page.locator("div#details_container div.internship_details")
                description = await desc_section.locator("div.text-container").first.inner_text()

                skills = await desc_section.locator("div.round_tabs_container").nth(0).all_inner_texts()

                certs = await desc_section.locator("div.training_link a").all_inner_texts()

                who_can_apply = await desc_section.locator("div.who_can_apply").all_inner_texts()

                perks = await desc_section.locator("h3.perks_heading + div.round_tabs_container span").all_inner_texts()

                openings = await desc_section.locator("h3:has-text('Number of openings') + div.text-container").inner_text()

                company_name = await desc_section.locator("h2.section_heading").nth(-1).inner_text()


                about_company = await desc_section.locator("div.about_company_text_container").inner_text()

                job_info={
                    "description": description,
                    "skills_required": skills,
                    "certifications": certs,
                    "who_can_apply": who_can_apply,
                    "perks": perks,
                    "openings": openings,
                    "company_name": company_name,
                    "about_company": about_company,
                    "Title":title,
                    "link":full_link
                }
                job_list.append(job_info)


            except Exception as e:
                print(f"❌ Skipped a job due to {e}")

        await browser.close()
        return job_list

async def apply_internshala_jobs(job_url,resume_path):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(storage_state="auth.json")
        page = await context.new_page()
        await page.goto(job_url)
        try:
            popup_close_btn = page.locator("#close_popup")
            if await popup_close_btn.is_visible(timeout=3000):
                await popup_close_btn.click()
                print("✅ Closed popup ad")
        except Exception as e:
            print(f"ℹ️ No popup or failed to close: {e}")


        await page.wait_for_selector("div#details_container div.internship_details div.buttons_container", timeout=5000)
        button_div=page.locator("div.buttons_container")
        apply_btn = button_div.locator("button#easy_apply_button")
        await apply_btn.wait_for(state="visible", timeout=15000)

        await apply_btn.scroll_into_view_if_needed()

        await apply_btn.click(force=True, timeout=3000)

        try:
            close_btn = page.locator("button.frame-close")
            await close_btn.click(timeout=2000)
            print("✅ Closed frame popup")
        except:
            print("ℹ️ No frame popup found")

        extra_inputs =  page.locator("form input, form textarea, form select")

        count = await extra_inputs.count()
        print(f"ℹ️ Found {count} extra fields")

        for i in range(count):
            element = extra_inputs.nth(i)
            tag = await element.evaluate("el => el.tagName.toLowerCase()")
            input_type = await element.evaluate("el => el.type || ''")
            name_attr = await element.get_attribute("name") or ""

            try:
                if input_type in ["file", "submit", "hidden"]:
                    continue

                if tag == "textarea":
                    await element.fill("This is my default answer for this question.")
                    print(f"✅ Filled textarea {name_attr}")

                elif tag == "input":
                    if input_type == "number":
                        await element.fill("0")
                        print(f"✅ Filled numeric field {name_attr}")
                    elif input_type in ["text", "email", "url"]:
                        await element.fill("Default answer")
                        print(f"✅ Filled text field {name_attr}")
                    elif input_type == "radio":
                        await page.locator("#loading_toast").wait_for(state="hidden", timeout=5000)

                        radio_id = await element.get_attribute("id")
                        if radio_id:
                            label = page.locator(f"label[for='{radio_id}']")
                            await label.click()
                            print(f"✅ Selected radio via label {name_attr}")
                        else:
                            await element.check(force=True)
                            print(f"✅ Selected radio {name_attr}")

                    elif input_type == "checkbox":
                        await element.check()
                        print(f"✅ Checked box {name_attr}")

                elif tag == "select":
                    options = await element.evaluate("el => Array.from(el.options).map(o => o.value)")
                    if options:
                        await element.select_option(options[0])  
                        print(f"✅ Selected dropdown {name_attr}")

            except Exception as e:
                print(f"⚠️ Could not fill {name_attr}: {e}")


        await page.locator("input#custom_resume").set_input_files(resume_path)
        print("✅ File uploaded")
        await page.wait_for_timeout(7000)
        await page.locator("input#submit").click()
        print("✅ Submitted application")
        await page.wait_for_timeout(9000)



async def login_internshala():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto("https://internshala.com/")
        login_btn = page.locator("button.login-cta")
        await login_btn.click()
        await page.wait_for_selector("#login-modal", state="visible")
        await page.fill("#modal_email", "tatanrata2@gmail.com")
        await page.fill("#modal_password", "dankdropdead")
        await page.click("#modal_login_submit")

        await page.wait_for_load_state("networkidle")
        await context.storage_state(path="auth.json")
        await browser.close()

