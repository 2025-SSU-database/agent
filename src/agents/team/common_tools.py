from langchain.tools import tool

@tool
def request_workspace_selection() -> str:
    """
    Request the user to select a workspace.
    Use this tool when you need a workspace_id to proceed (e.g., for creating a project) but one was not provided or is ambiguous.
    The user will be presented with a UI to select a workspace.
    """
    return "[UI_REQUEST] SELECT_WORKSPACE"

@tool
def request_project_selection(workspace_id: str) -> str:
    """
    Request the user to select a project within a specific workspace.
    Use this tool when you need a project_id to proceed (e.g., for creating a backlog) but one was not provided or is ambiguous.
    The user will be presented with a UI to select a project from the given workspace.
    
    Args:
        workspace_id: The ID of the workspace to list projects from.
    """
    return f"[UI_REQUEST] SELECT_PROJECT workspace_id={workspace_id}"
