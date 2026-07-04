def attach_diagnostics(page, sitemap_page_record: dict):
    sitemap_page_record.setdefault("console_errors", [])
    sitemap_page_record.setdefault("console_warnings", [])
    sitemap_page_record.setdefault("failed_requests", [])

    def on_console(msg):
        if msg.type == "error":
            sitemap_page_record["console_errors"].append(msg.text[:500])
        elif msg.type == "warning":
            sitemap_page_record["console_warnings"].append(msg.text[:500])

    def on_response(response):
        try:
            if response.status >= 400:
                sitemap_page_record["failed_requests"].append({
                    "url": response.url, "status": response.status
                })
        except Exception:
            pass

    def on_pageerror(exc):
        sitemap_page_record["console_errors"].append(f"Uncaught: {str(exc)[:500]}")

    page.on("console", on_console)
    page.on("response", on_response)
    page.on("pageerror", on_pageerror)

    return on_console, on_response, on_pageerror  

def detach_diagnostics(page, handles):
    on_console, on_response, on_pageerror = handles
    try:
        page.remove_listener("console", on_console)
        page.remove_listener("response", on_response)
        page.remove_listener("pageerror", on_pageerror)
    except Exception:
        pass