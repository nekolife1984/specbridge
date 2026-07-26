# @verifies 1.1
def test_create_task():
    from src.tasks.service import create_task
    task = create_task("Buy milk")
    assert task["title"] == "Buy milk"
    assert task["id"] is not None


# @verifies 1.1.1
def test_title_validation():
    from src.tasks.service import create_task
    import pytest
    with pytest.raises(ValueError):
        create_task("")


# @verifies 1.2
def test_list_tasks():
    from src.tasks.service import create_task, list_tasks
    create_task("A")
    create_task("B")
    assert len(list_tasks()) >= 2
