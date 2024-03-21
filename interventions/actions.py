

def show_div(html: str):
    return {
        "action": "ShowDiv",
        "data": {
            "html": html,
        }
    }

def show_message(message: str):
    return {
        "action": "ShowMessage",
        "data": {
            "message": message,
        }
    }

def highlight_code(start_line: int, end_line: int, start_column: int, end_column: int, message: str = None):
    return {
        "action": "HighlightCode",
        "data": {
            "startLine": start_line,
            "endLine": end_line,
            "startColumn": start_column,
            "endColumn": end_column,
            "message": message
        }
    }

def custom_action(action: str, data: dict[str, any]):
    if not action.startswith("X-"):
        # Actions not in the specification, start with "X-"
        action = "X-" + action
    return {
        "action": action,
        "data": data
    }