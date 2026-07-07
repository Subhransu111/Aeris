def mock_response(action: dict) -> dict:
    return {
        "mocked": True,
        "status": "success",
        "action_type": action["type"],
        "note": "Real action blocked; synthetic success returned"
    }