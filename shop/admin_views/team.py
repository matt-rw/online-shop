"""
Team dashboard admin views — tasks, projects, and team members.
"""

import json
from datetime import datetime

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from shop.models.messaging import Project, Task, TeamMember

User = get_user_model()


@staff_member_required
def team_dashboard(request):
    """Team dashboard with kanban tasks, projects, and team member management."""

    if request.method == "POST":
        action = request.POST.get("action")

        # --- Task actions ---
        if action == "task_add":
            try:
                due_date = request.POST.get("due_date") or None
                project_id = request.POST.get("project") or None
                assigned_id = request.POST.get("assigned_to") or None
                task = Task.objects.create(
                    title=request.POST.get("title", ""),
                    priority=request.POST.get("priority", "medium"),
                    assigned_to_id=assigned_id,
                    due_date=due_date,
                    project_id=project_id,
                    created_by=request.user,
                )
                return JsonResponse({"success": True, "id": task.id})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "task_update":
            try:
                task = get_object_or_404(Task, id=request.POST.get("task_id"))
                task.title = request.POST.get("title", task.title)
                task.status = request.POST.get("status", task.status)
                task.priority = request.POST.get("priority", task.priority)
                assigned_id = request.POST.get("assigned_to")
                if assigned_id is not None:
                    task.assigned_to_id = assigned_id or None
                project_id = request.POST.get("project")
                if project_id is not None:
                    task.project_id = project_id or None
                if task.status == "done" and not task.completed_at:
                    task.completed_at = timezone.now()
                elif task.status != "done":
                    task.completed_at = None
                task.save()
                return JsonResponse({"success": True})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "task_delete":
            try:
                task = get_object_or_404(Task, id=request.POST.get("task_id"))
                task.delete()
                return JsonResponse({"success": True})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "task_move":
            try:
                task = get_object_or_404(Task, id=request.POST.get("task_id"))
                new_status = request.POST.get("status")
                task.status = new_status
                if new_status == "done" and not task.completed_at:
                    task.completed_at = timezone.now()
                elif new_status != "done":
                    task.completed_at = None
                task.save()
                return JsonResponse({"success": True})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        # --- Project actions ---
        elif action == "project_add":
            try:
                project = Project.objects.create(
                    name=request.POST.get("name", ""),
                    description=request.POST.get("description", ""),
                    created_by=request.user,
                )
                return JsonResponse({"success": True, "id": project.id})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "project_update":
            try:
                project = get_object_or_404(Project, id=request.POST.get("project_id"))
                project.name = request.POST.get("name", project.name)
                project.description = request.POST.get("description", project.description)
                project.status = request.POST.get("status", project.status)
                project.save()
                return JsonResponse({"success": True})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "project_delete":
            try:
                project = get_object_or_404(Project, id=request.POST.get("project_id"))
                project.delete()
                return JsonResponse({"success": True})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        # --- Team actions ---
        elif action == "team_add":
            try:
                user = get_object_or_404(User, id=request.POST.get("user_id"))
                member, created = TeamMember.objects.get_or_create(
                    user=user,
                    defaults={
                        "display_name": request.POST.get("display_name", user.first_name or user.username),
                        "role": request.POST.get("role", "other"),
                    }
                )
                if not created:
                    return JsonResponse({"success": False, "error": "Already a team member"})
                return JsonResponse({"success": True, "id": member.id})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "team_update":
            try:
                member = get_object_or_404(TeamMember, id=request.POST.get("member_id"))
                member.display_name = request.POST.get("display_name", member.display_name)
                member.role = request.POST.get("role", member.role)
                member.save()
                return JsonResponse({"success": True})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "team_avatar":
            try:
                member = get_object_or_404(TeamMember, id=request.POST.get("member_id"))
                if "avatar" in request.FILES:
                    member.avatar = request.FILES["avatar"]
                    member.save()
                return JsonResponse({"success": True})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        return JsonResponse({"success": False, "error": "Unknown action"})

    # --- GET: auto-create TeamMember for any staff user who doesn't have one ---
    for staff_user in User.objects.filter(is_staff=True):
        TeamMember.objects.get_or_create(
            user=staff_user,
            defaults={
                "display_name": staff_user.first_name or staff_user.username,
                "role": "other",
            }
        )

    team_members = TeamMember.objects.filter(is_active=True).annotate(
        task_count=Count(
            "user__assigned_tasks",
            filter=Q(user__assigned_tasks__status__in=["todo", "in_progress"]),
        ),
    )

    # Tasks JSON — exclude archived project tasks
    tasks = Task.objects.exclude(
        project__status="archived"
    ).select_related("assigned_to", "created_by", "project")

    # Build a user_id -> team_member_id lookup
    user_to_team = {m.user_id: m.id for m in team_members}

    tasks_data = []
    for t in tasks:
        assignee_name = ""
        assignee_team_id = None
        if t.assigned_to:
            assignee_name = t.assigned_to.get_full_name() or t.assigned_to.username
            assignee_team_id = user_to_team.get(t.assigned_to_id)
        tasks_data.append({
            "id": t.id,
            "title": t.title,
            "status": t.status,
            "priority": t.priority,
            "assignee": assignee_name,
            "assigned_to": assignee_team_id,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "project_id": t.project_id,
            "created_by": t.created_by.get_full_name() or t.created_by.username if t.created_by else "",
        })

    # Projects JSON — active only
    projects = Project.objects.filter(status="active").annotate(
        open_count=Count("tasks", filter=Q(tasks__status__in=["todo", "in_progress"])),
        done_count=Count("tasks", filter=Q(tasks__status="done")),
    )
    projects_data = [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "open_count": p.open_count,
            "done_count": p.done_count,
        }
        for p in projects
    ]

    # Team JSON
    team_data = []
    for m in team_members:
        team_data.append({
            "id": m.id,
            "name": m.display_name,
            "role": m.role,
            "avatar_url": m.avatar.url if m.avatar else None,
            "task_count": m.task_count,
        })

    staff_users = User.objects.filter(is_staff=True)

    context = {
        "team_members": team_members,
        "projects": projects,
        "tasks_json": json.dumps(tasks_data),
        "projects_json": json.dumps(projects_data),
        "team_json": json.dumps(team_data),
        "staff_users": staff_users,
    }
    return render(request, "admin/team_dashboard.html", context)


@staff_member_required
def team_members_page(request):
    """Team members management — create users, edit profiles, manage access."""

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "create_user":
            try:
                username = request.POST.get("username", "").strip()
                email = request.POST.get("email", "").strip()
                first_name = request.POST.get("first_name", "").strip()
                password = request.POST.get("password", "").strip()
                display_name = request.POST.get("display_name", "").strip() or first_name or username
                role = request.POST.get("role", "other")

                if not username or not email:
                    return JsonResponse({"success": False, "error": "Username and email required"})
                if User.objects.filter(username=username).exists():
                    return JsonResponse({"success": False, "error": "Username already exists"})
                if User.objects.filter(email=email).exists():
                    return JsonResponse({"success": False, "error": "Email already exists"})

                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password or "changeme123",
                    first_name=first_name,
                    is_staff=True,
                )
                TeamMember.objects.create(
                    user=user,
                    display_name=display_name,
                    role=role,
                )
                return JsonResponse({"success": True, "id": user.id})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "add_existing":
            try:
                user = get_object_or_404(User, id=request.POST.get("user_id"))
                display_name = request.POST.get("display_name", "").strip() or user.first_name or user.username
                role = request.POST.get("role", "other")
                member, created = TeamMember.objects.get_or_create(
                    user=user,
                    defaults={"display_name": display_name, "role": role}
                )
                if not created:
                    return JsonResponse({"success": False, "error": "Already a team member"})
                return JsonResponse({"success": True, "id": member.id})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "update_member":
            try:
                member = get_object_or_404(TeamMember, id=request.POST.get("member_id"))
                user = member.user
                # Update user fields
                email = request.POST.get("email", "").strip()
                if email and email != user.email:
                    if User.objects.filter(email=email).exclude(id=user.id).exists():
                        return JsonResponse({"success": False, "error": "Email already in use"})
                    user.email = email
                first_name = request.POST.get("first_name", "").strip()
                if first_name:
                    user.first_name = first_name
                user.save()
                # Update team member fields
                display_name = request.POST.get("display_name", "").strip()
                if display_name:
                    member.display_name = display_name
                role = request.POST.get("role")
                if role:
                    member.role = role
                member.save()
                return JsonResponse({"success": True})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "upload_avatar":
            try:
                member = get_object_or_404(TeamMember, id=request.POST.get("member_id"))
                if "avatar" in request.FILES:
                    member.avatar = request.FILES["avatar"]
                    member.save()
                return JsonResponse({"success": True, "url": member.avatar.url if member.avatar else None})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "remove_member":
            try:
                member = get_object_or_404(TeamMember, id=request.POST.get("member_id"))
                member.is_active = False
                member.save()
                return JsonResponse({"success": True})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

    # GET — auto-create TeamMember for any staff user who doesn't have one
    for staff_user in User.objects.filter(is_staff=True):
        TeamMember.objects.get_or_create(
            user=staff_user,
            defaults={
                "display_name": staff_user.first_name or staff_user.username,
                "role": "other",
            }
        )

    members = TeamMember.objects.filter(is_active=True).select_related("user").annotate(
        task_count=Count(
            "user__assigned_tasks",
            filter=Q(user__assigned_tasks__status__in=["todo", "in_progress"]),
        ),
    )
    # Staff users not yet team members
    existing_team_user_ids = TeamMember.objects.filter(is_active=True).values_list("user_id", flat=True)
    available_staff = User.objects.filter(is_staff=True).exclude(id__in=existing_team_user_ids)

    context = {
        "members": members,
        "available_staff": available_staff,
    }
    return render(request, "admin/team_members.html", context)
