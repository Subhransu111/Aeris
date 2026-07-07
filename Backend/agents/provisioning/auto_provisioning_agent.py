"""
Config-driven account provisioning: the developer supplies exact field
values via the platform's onboarding form (registration_config). This
agent's job is purely mechanical - match config entries to real form
fields (by name/type, since actual selectors change between crawls) and
fill/submit/step-through, with safety nets for CAPTCHA/OAuth still active
in case the config becomes stale (e.g. app was redesigned).
"""
from Backend.core.core.action_wrapper import execute_action
from Backend.agents.provisioning.blocker_detector import detect_blocker
from Backend.agents.provisioning.success_detector import detect_registration_success


def _extract_current_form_fields(page) -> list:
    return page.evaluate("""
        () => {
            const forms = Array.from(document.querySelectorAll('form'));
            const getSelector = (el) => {
                if (el.id) return '#' + CSS.escape(el.id);
                if (el.name) return `[name="${el.name}"]`;
                const path = [];
                let node = el;
                while (node && node.tagName && path.length < 5) {
                    let sel = node.tagName.toLowerCase();
                    const parent = node.parentElement;
                    if (parent) {
                        const siblings = Array.from(parent.children).filter(c => c.tagName === node.tagName);
                        if (siblings.length > 1) sel += `:nth-of-type(${siblings.indexOf(node)+1})`;
                    }
                    path.unshift(sel);
                    node = parent;
                }
                return path.join(' > ');
            };
            if (forms.length === 0) return [];
            const form = forms[0];
            const fields = [];
            form.querySelectorAll('input, select, textarea').forEach(inp => {
                if (inp.type === 'hidden' || inp.type === 'submit') return;
                fields.push({
                    name: (inp.getAttribute('name') || '').toLowerCase(),
                    type: (inp.getAttribute('type') || inp.tagName.toLowerCase()).toLowerCase(),
                    placeholder: (inp.getAttribute('placeholder') || '').toLowerCase(),
                    selector: getSelector(inp),
                });
            });
            return fields;
        }
    """)


def _match_config_field(real_field: dict, config_fields: list) -> dict:
    """
    Matches a real DOM field to a config entry by type + fuzzy name match.
    The developer's config uses their own field names/hints; the actual
    crawled DOM field has its own name/placeholder - this bridges them
    without requiring exact string equality.
    """
    for cfg in config_fields:
        hint = cfg["selector_hint"].lower()
        if cfg["type"].lower() == real_field["type"] and (
            hint in real_field["name"] or hint in real_field["placeholder"] or real_field["name"] in hint
        ):
            return cfg
    # Fallback: match by type alone if only one config field of that type exists
    same_type = [c for c in config_fields if c["type"].lower() == real_field["type"]]
    if len(same_type) == 1:
        return same_type[0]
    return None


def _fill_step(page, config_fields: list, agent_id: str, base_domain: str, verified_domain: str) -> list:
    action = {"type": "form_submit", "target_domain": base_domain, "verified_domain": verified_domain}
    decision = execute_action(agent_id, action, sandbox_mode=True)
    if decision["status"] != "executed":
        return None  # policy blocked

    real_fields = _extract_current_form_fields(page)
    unmatched = []

    for real_field in real_fields:
        match = _match_config_field(real_field, config_fields)
        if not match:
            unmatched.append(real_field)
            continue
        try:
            if real_field["type"] == "checkbox":
                page.check(real_field["selector"], timeout=2000)
            else:
                page.fill(real_field["selector"], str(match["value"]), timeout=2000)
        except Exception:
            continue

    return unmatched


def provision_account_from_config(page, registration_config: dict, base_domain: str, verified_domain: str,
                                     agent_id: str = "provisioning_agent", max_steps: int = 5) -> dict:
    """
    Uses the developer-supplied registration_config to fill and submit the
    signup form, stepping through additional_steps if the form is
    multi-step. Returns login-ready credentials from the same config.
    """
    log = []
    signup_url = registration_config["signup_url"]

    try:
        page.goto(signup_url, wait_until="load", timeout=15000)
        page.wait_for_timeout(1000)
    except Exception as e:
        return {"status": "failed", "reason": "page_load_failed", "detail": str(e), "log": log}

    blocker = detect_blocker(page)
    if blocker["blocked"]:
        return {"status": "unsupported", "reason": blocker["reason"], "log": log}

    all_steps = [{"step_name": "main", "fields": registration_config["fields"]}] + \
                registration_config.get("additional_steps", [])

    for i, step in enumerate(all_steps):
        unmatched = _fill_step(page, step["fields"], agent_id, base_domain, verified_domain)
        if unmatched is None:
            return {"status": "failed", "reason": "policy_blocked", "log": log}

        log.append({"step": step["step_name"], "unmatched_fields": [f["name"] for f in unmatched]})

        submit_text = registration_config.get("submit_button_text")
        try:
            if submit_text:
                page.click(f"button:has-text('{submit_text}')", timeout=5000)
            else:
                page.click("form button[type=submit], form button", timeout=5000)
        except Exception as e:
            return {"status": "failed", "reason": "submit_click_failed", "detail": str(e)[:200], "log": log}

        page.wait_for_timeout(1500)
        try:
            page.wait_for_load_state("load", timeout=8000)
        except Exception:
            pass

        blocker = detect_blocker(page)
        if blocker["blocked"]:
            return {"status": "unsupported", "reason": blocker["reason"], "log": log}

        # Last step -> check for success. Intermediate steps -> just continue.
        if i == len(all_steps) - 1:
            success_check = detect_registration_success(page, signup_url)
            log.append({"final_success_check": success_check})
            if not success_check["success"]:
                return {"status": "failed", "reason": success_check["reason"], "log": log}

    return {
        "status": "success",
        "credentials": {
            "username": registration_config["login_identifier_value"],
            "password": registration_config["login_password_value"],
        },
        "login_url": registration_config.get("login_url"),
        "log": log,
    }