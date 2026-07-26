# @module tasks
# @feature create_task
# @impl 1.1
def create_task(title: str, description: str = "") -> dict:
    """Create a new task."""
    _validate_title(title)
    task = {
        "id": _generate_id(),
        "title": title,
        "description": description,
        "done": False,
    }
    _store.append(task)
    return task


_store: list[dict] = []


def _validate_title(title: str) -> None:
    # @impl 1.1.1
    if not title or len(title) > 200:
        raise ValueError("Title must be 1-200 characters")


def _generate_id() -> str:
    import uuid
    return str(uuid.uuid4())


# @impl 1.2
def list_tasks() -> list[dict]:
    """List all tasks sorted by creation date."""
    return sorted(_store, key=lambda t: t.get("created_at", ""))
