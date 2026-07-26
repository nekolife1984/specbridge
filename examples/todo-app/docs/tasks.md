<!-- @spec 1.1 -->
# Task Creation

Users can create tasks with a title and description.

_Boundary:_ src/tasks/

## API Design
<!-- @design TaskCreateRequest -->

The POST /api/tasks endpoint accepts JSON body
with `title` (required) and `description` (optional).

## Implementation Notes

- Validate title length (1-200 chars)
- Generate UUID for each task
- Store in in-memory list

<!-- @spec 1.1.1 -->
### Title Validation

Title must be between 1 and 200 characters.
Empty titles are rejected with 400 Bad Request.

<!-- @spec 1.2 -->
# Task Listing

Users can list all tasks, sorted by creation date.

_Boundary:_ src/tasks/
