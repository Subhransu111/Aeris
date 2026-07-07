def format_report_markdown(report: dict, app_name: str = "Application") -> str:
    md = f"# Aegis AI Engineering Report: {app_name}\n\n"
    md += f"## Executive Summary\n\n{report.get('executive_summary', 'N/A')}\n\n"

    score = report.get("launch_readiness_score", "N/A")
    md += f"## Launch Readiness Score: {score}/100\n\n{report.get('launch_readiness_reasoning', '')}\n\n"

    root_causes = report.get("root_cause_findings", [])
    if root_causes:
        md += "## Root Cause Analysis\n\n"
        for rc in root_causes:
            md += f"### {rc.get('root_cause')} — *{rc.get('severity', '').upper()}*\n\n"
            md += f"**Business impact:** {rc.get('business_impact')}\n\n"
            md += f"**Technical detail:** {rc.get('technical_detail')}\n\n"
            md += f"**Estimated effort:** {rc.get('estimated_effort')}\n\n"
            md += "**Symptoms observed:**\n"
            for s in rc.get("symptoms", []):
                md += f"- {s}\n"
            md += "\n**Affected locations:**\n"
            for loc in rc.get("affected_locations", []):
                md += f"- {loc}\n"
            md += "\n"

    priorities = report.get("priority_ranking", [])
    if priorities:
        md += "## Priority Ranking\n\n"
        md += "| Priority | Issue | Severity | Effort |\n|---|---|---|---|\n"
        for p in priorities:
            md += f"| {p.get('priority')} | {p.get('issue')} | {p.get('severity')} | {p.get('estimated_effort')} |\n"
        md += "\n"

    domain_summaries = report.get("domain_summaries", {})
    if domain_summaries:
        md += "## Domain Summaries\n\n"
        for domain, text in domain_summaries.items():
            md += f"**{domain.capitalize()}:** {text}\n\n"

    if report.get("coverage_notes"):
        md += f"## Test Coverage Notes\n\n{report['coverage_notes']}\n\n"

    roadmap = report.get("roadmap", [])
    if roadmap:
        md += "## Roadmap\n\n"
        for w in sorted(roadmap, key=lambda x: x.get("week", 99)):
            md += f"### Week {w.get('week')}: {w.get('focus')}\n"
            for action in w.get("actions", []):
                md += f"- {action}\n"
            md += "\n"

    return md