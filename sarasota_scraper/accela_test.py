from playwright.sync_api import sync_playwright

def test_accela_portal():
    # 1. Start the Playwright engine using a context manager
    with sync_playwright() as p:
        # 2. Launch Chromium in visible mode (headless=False)
        browser = p.chromium.launch(headless=False)
        
        # 3. Create a fresh, isolated browser context
        context = browser.new_context()
        
        # 4. Open a new page/tab within that context
        page = context.new_page()
        
        print("Navigating to the Accela Building portal...")
        url = "https://aca-prod.accela.com/BOCC/Cap/CapHome.aspx?module=Building"
        page.goto(url)
        
        print("Page loaded! Opening Playwright Inspector...")
        # 5. Pause execution so we can visually inspect the page
        page.pause()
        
        # Clean up
        browser.close()

if __name__ == "__main__":
    test_accela_portal()