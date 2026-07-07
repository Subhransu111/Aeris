"""
Walks the sitemap's navigation_graph + page classifications to find
sequences matching known journey patterns. This treats the crawl output
as a graph-search problem: does a path exist from a landing-classified
page through the required intermediate classifications to the target?
"""
from Backend.agents.journey.journey_definitions import JOURNEY_PATTERNS


def _build_classification_map(sitemap: dict) -> dict:
    """page_key -> classification, url -> page_key for lookup."""
    return {key: data.get("classification") for key, data in sitemap["pages"].items() if data.get("reachable")}


def _find_page_by_classification(sitemap: dict, classification: str) -> list:
    return [key for key, data in sitemap["pages"].items()
            if data.get("classification") == classification and data.get("reachable")]


def _path_exists(nav_graph: dict, start: str, target_classification: str, class_map: dict,
                  max_depth: int = 6, visited: set = None) -> list:
    """BFS from start looking for any reachable page with target_classification.
    Returns the path (list of page_keys) if found, else None."""
    visited = visited or set()
    queue = [(start, [start])]

    while queue:
        current, path = queue.pop(0)
        if len(path) > max_depth:
            continue
        if current in visited:
            continue
        visited.add(current)

        if class_map.get(current) == target_classification and current != start:
            return path

        for neighbor in nav_graph.get(current, []):
            if neighbor not in visited:
                queue.append((neighbor, path + [neighbor]))

    return None


def detect_journeys(sitemap: dict) -> list:
    """
    Returns list of detected journeys: {name, description, path (list of
    page_keys), matched: bool}. A journey is 'matched' if a real navigation
    path connecting the required classifications was found in the crawl data.
    """
    nav_graph = sitemap.get("navigation_graph", {})
    class_map = _build_classification_map(sitemap)
    detected = []

    for pattern in JOURNEY_PATTERNS:
        sequence = pattern["sequence"]
        start_candidates = _find_page_by_classification(sitemap, sequence[0])

        best_path = None
        for start in start_candidates:
            current_path = [start]
            current_node = start
            success = True

            for target_class in sequence[1:]:
                sub_path = _path_exists(nav_graph, current_node, target_class, class_map)
                if not sub_path:
                    success = False
                    break
                current_path.extend(sub_path[1:])
                current_node = sub_path[-1]

            if success:
                best_path = current_path
                break

        detected.append({
            "journey_name": pattern["name"],
            "description": pattern["description"],
            "matched": best_path is not None,
            "path": best_path,
        })

    return detected