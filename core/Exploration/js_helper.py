"""
Shared JS snippet injected into every page.evaluate() call that needs to
identify an element. Centralized here so selector strategy stays consistent
across static extraction, modal dismissal, and interaction discovery.

Selector priority: data-testid > id > aria-label > generated nth-of-type path.
The first three are stable across re-renders; the path fallback is best-effort
for markup that gives us nothing better (common with div-as-button components).
"""

GET_SELECTOR_JS = r"""
function getSelector(el) {
    if (!el) return null;
    if (el.dataset && el.dataset.testid) return `[data-testid="${el.dataset.testid}"]`;
    if (el.id) return `#${CSS.escape(el.id)}`;
    const aria = el.getAttribute('aria-label');
    if (aria) return `${el.tagName.toLowerCase()}[aria-label="${aria.replace(/"/g, '\\"')}"]`;

    // Prefer matching by visible text for nav/button-like elements when no
    // stable attribute exists -- class names on modern component frameworks
    // are frequently state-dependent (scroll position, active tab, etc.)
    // and can vanish or change between the moment we extract and the
    // moment we act, making a class-based selector silently stale.
    const text = (el.innerText || el.value || '').trim();
    if (text && text.length < 40 && (el.tagName === 'BUTTON' || el.tagName === 'A' || el.getAttribute('role') === 'button')) {
        const tag = el.tagName.toLowerCase();
        return `xpath=//${tag}[normalize-space(text())="${text.replace(/"/g, '')}"]`;
    }

    let path = [];
    let node = el;
    let depth = 0;
    while (node && node.nodeType === 1 && depth < 5) {
        let selector = node.tagName.toLowerCase();
        if (typeof node.className === 'string' && node.className.trim()) {
            const cls = node.className.trim().split(/\s+/).slice(0, 2).join('.');
            selector += '.' + CSS.escape(cls).replace(/\\\./g, '.');
        }
        const parent = node.parentElement;
        if (parent) {
            const siblings = Array.from(parent.children).filter(c => c.tagName === node.tagName);
            if (siblings.length > 1) {
                selector += `:nth-of-type(${siblings.indexOf(node) + 1})`;
            }
        }
        path.unshift(selector);
        node = parent;
        depth++;
    }
    return path.join(' > ');
}
"""