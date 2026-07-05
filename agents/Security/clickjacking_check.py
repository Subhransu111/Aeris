def check_clickjacking(page, target_url: str) -> dict:
    test_html = f"""
    <html>
        <head><title>Clickjacking Test</title></head>
        <body>
            <iframe id="test-frame" src="{target_url}" width="500" height="500"></iframe>
        </body>
    </html>
    """
    try:
        page.set_content(test_html)
        page.wait_for_timeout(2000) 
        
        frame_element = page.locator("#test-frame")
        
        # 3. Use Playwright to check if the frame content is accessible and rendered
        # If blocked by X-Frame-Options, the frame content will be empty or an browser error page
        child_frames = page.main_frame.child_frames
        
        frame_loaded = False
        if child_frames:
            target_frame = child_frames[0]
            try:
                current_url = target_frame.url
                if current_url == target_url or target_url in current_url:
                    frame_loaded = True
            except Exception:
                frame_loaded = False

        return {
            "check": "clickjacking",
            "outcome": "vulnerable" if frame_loaded else "protected",
            "severity": "high" if frame_loaded else "info", # Clickjacking is usually High/Moderate depending on context
            "detail": "Target page successfully embedded in a cross-origin iframe." if frame_loaded 
                      else "Iframe embedding blocked by browser security policies.",
        }
    except Exception as e:
        return {"check": "clickjacking", "outcome": "check_failed", "detail": str(e)[:200]}