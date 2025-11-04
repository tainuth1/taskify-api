<!-- 48227cac-72f2-4243-88a6-8177145b6333 d73f63f5-d64a-4dc0-87e3-8ffcd9f829c1 -->
# Project Fetching and Access Control Implementation

## Overview

Implement proper project fetching with role-based access control. Personal projects are only visible to owners, group projects are accessible to active members. Add a project detail endpoint with structured response for future task/subtask/comment integration.

## Current State Analysis

- `create_project` already stores owner in `project_members` table for both personal and group projects
- `get_all_projects` fetches projects via JOIN with `project_members` but doesn't distinguish personal vs group filtering
- Need to add proper filtering logic and a project detail endpoint

## Implementation Plan

### 1. Update `get_all_projects` Query Logic

**File: `app/controllers/project_controller.py`**

Current query fetches all projects where user is active member. Need to add filtering:

- **Personal projects**: Only show if `project.type == personal` AND `project_member.role == owner`
- **Group projects**: Show if user is any active member (`status == active`)

Query pattern:

```python
# Option 1: Two separate queries combined
# Option 2: Single query with OR condition for (personal+owner) OR (group+member)
```

### 2. Create `get_project_by_id` Method

**File: `app/controllers/project_controller.py`**

- Validate token and get user_id
- Check project exists
- Verify access:
  - Personal: user must be owner
  - Group: user must be active member
- Return `ProjectDetailResponse` with structure for tasks/subtasks/comments
- Raise 404 if no access

### 3. Create Permission Helper Methods

**File: `app/controllers/project_controller.py`**

- `_check_project_access(user_id, project_id, db)` → bool
  - Returns True if user has access, False otherwise
- `_get_user_project_role(user_id, project_id, db)` → MemberRole | None
  - Returns user's role in project or None if no access

### 4. Create Project Detail Response Schema

**File: `app/schemas/project.py`**

Add `ProjectDetailResponse` schema with:

- All fields from `ProjectResponse`
- `tasks: List[dict]` (empty for now, structure for future)
- `subtasks: List[dict]` (empty for now, structure for future)
- `comments: List[dict]` (empty for now, structure for future)
- User's role in the project

### 5. Add GET `/projects/{project_id}` Endpoint

**File: `app/api/endpoints/project.py`**

- Extract project_id from path
- Call controller method
- Return structured response or 404

### 6. Update Project Response Structure

Ensure `ProjectResponse` and detail response properly serialize members list with user data and roles.

## Query Patterns

### For `get_all_projects`:

```python
# Approach: Single query with OR conditions
projects = (
    db.query(ProjectModel)
    .join(ProjectMember, ProjectMember.project_id == ProjectModel.id)
    .filter(ProjectMember.user_id == user_id)
    .filter(ProjectMember.status == MemberStatus.active)
    .filter(
        or_(
            # Personal: must be owner
            and_(
                ProjectModel.type == ProjectTypeModel.personal,
                ProjectMember.role == MemberRole.owner
            ),
            # Group: any active member
            ProjectModel.type == ProjectTypeModel.group
        )
    )
    .all()
)
```

### For `get_project_by_id`:

```python
# First check if project exists
project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
if not project:
    raise ValueError("Project not found")

# Check membership
member = (
    db.query(ProjectMember)
    .filter(ProjectMember.project_id == project_id)
    .filter(ProjectMember.user_id == user_id)
    .filter(ProjectMember.status == MemberStatus.active)
    .first()
)

# Personal projects: must be owner
if project.type == ProjectTypeModel.personal:
    if not member or member.role != MemberRole.owner:
        raise ValueError("Access denied")
# Group projects: must be active member
else:
    if not member:
        raise ValueError("Access denied")
```

## Files to Modify

1. `app/controllers/project_controller.py`

   - Update `get_all_projects` method
   - Add `get_project_by_id` method
   - Add helper methods `_check_project_access` and `_get_user_project_role`

2. `app/schemas/project.py`

   - Add `ProjectDetailResponse` schema

3. `app/api/endpoints/project.py`

   - Add `GET /projects/{project_id}` endpoint

## Notes

- Non-members are blocked via permission checks
- Personal projects filtered to owners only
- Group projects accessible to all active members (equal access for now)
- Detail endpoint includes structure for tasks/subtasks/comments (empty lists for now)
- All endpoints validate JWT token from cookies

### To-dos

- [ ] Update get_all_projects method to filter personal projects (owner only) and group projects (any active member)
- [ ] Create _check_project_access and _get_user_project_role helper methods in ProjectController
- [ ] Create ProjectDetailResponse schema with tasks/subtasks/comments structure in project.py schemas
- [ ] Implement get_project_by_id method in ProjectController with permission checks
- [ ] Add GET /projects/{project_id} endpoint in project.py router