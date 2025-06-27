from typing import List
from schemas import ProjectInviteRequest, UserInvite
from email_utils import EmailService
from supabase import create_client
import uuid
from sklearn.cluster import KMeans
import numpy as np
import google.generativeai as genai
# Import ML and AI libraries with error handling
try:
    
    ML_AVAILABLE = True
    GEMINI_AVAILABLE = True
    # Configure Gemini
    GEMINI_API_KEY = "AIzaSyDCR2OIefMry0tuTbvNM4mRPDxQpl2BIRw"
    genai.configure(api_key=GEMINI_API_KEY)
except ImportError as e:
    print(f"Warning: Some ML/AI libraries not available: {e}")
    ML_AVAILABLE = False
    GEMINI_AVAILABLE = False

SUPABASE_URL = "https://clpsxwgujflkbqtnxdca.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNscHN4d2d1amZsa2JxdG54ZGNhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDkwNDcwMjIsImV4cCI6MjA2NDYyMzAyMn0.FU6LugpZ1T5Dvbc49lj5kWa8rb31uIFCydtlHAibEAg"

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def invite_users_to_project(payload: ProjectInviteRequest):
    invited = []
    for user in payload.users:
        # 1. Look up user by email
        user_lookup = supabase.table("users").select("user_id").eq("email", user.email).execute()
        if not user_lookup.data or len(user_lookup.data) != 1:
            print(f"[ERROR] User with email {user.email} not found or not unique")
            raise ValueError(f"User with email {user.email} not found or not unique")
        user_id = user_lookup.data[0]["user_id"]

        # 2. Get org_id and project_name for the project
        project_resp = supabase.table("projects").select("org_id, project_name").eq("project_id", payload.project_id).single().execute()
        if not project_resp.data:
            print(f"[ERROR] Project with id {payload.project_id} not found")
            raise ValueError("Project not found")
        org_id = project_resp.data["org_id"]
        project_name = project_resp.data["project_name"]

        # 3. Ensure user is in organization_members
        org_member_check = supabase.table("organization_members") \
            .select("user_id") \
            .eq("user_id", user_id) \
            .eq("org_id", org_id) \
            .execute()
        if not org_member_check.data:
            supabase.table("organization_members").insert({
                "user_id": user_id,
                "org_id": org_id,
                "role": "org_member",
                "status": "active"
            }).execute()
            print(f"[INFO] Added user {user.email} (id: {user_id}) to organization {org_id}")

        # 4. Check if this user is already in the project
        exists_check = supabase.table("project_members") \
            .select("user_id") \
            .eq("user_id", user_id) \
            .eq("project_id", payload.project_id) \
            .execute()
        if exists_check.data:
            # Removed print for duplicate skip
            continue  # skip this user

        # 5. Insert into project_members
        insert_resp = supabase.table("project_members").insert({
            "user_id": user_id,
            "project_id": payload.project_id,
            "role": user.role.value,
        }).execute()
        if insert_resp.status_code != 201:
            print(f"[ERROR] Failed to add user {user.email} to project {payload.project_id}: {insert_resp.json()}")
            raise ValueError(f"Insertion failed with status {insert_resp.status_code}: {insert_resp.json()}")
        print(f"[INFO] Added user {user.email} (id: {user_id}) to project {payload.project_id} as {user.role.value}")

        # 6. Send invite email with project name
        email_service = EmailService()
        try:
            email_service.send_participant_invite(user.email, project_name, "You've been added to a project.")
            print(f"[EMAIL] Invite sent to {user.email} for project '{project_name}'")
        except Exception as e:
            print(f"[EMAIL][ERROR] Failed to send invite to {user.email}: {str(e)}")
        invited.append(user.email)
    return invited

def notify_meeting_link(payload):
    
    results = []
    for email in payload.participants:
        try:
            subject = f"Meeting Link for Project {payload.project_id}"
            body = f"""
            Hello,

            A meeting has been scheduled under Project `{payload.project_id}`.
            Join using the link: {payload.link}

            Meeting ID: {payload.meeting_id}

            - Momentum AI Team
            """
            email_service = EmailService()
            email_service.send_participant_invite(email, payload.project_id, "You've been invited to a meeting.")
            print(f"[EMAIL] Meeting link sent to {email} for project {payload.project_id}")
            results.append(f"Sent link to {email}")
        except Exception as e:
            print(f"[EMAIL][ERROR] Failed to send meeting link to {email}: {str(e)}")
            results.append(f"Failed to send to {email}: {str(e)}")
    return results

# ==================== Context Grouping ====================

def fetch_project_summaries(project_id: str):
    """Fetch all summaries for a project"""
    if not ML_AVAILABLE or not GEMINI_AVAILABLE:
        raise ValueError("ML or AI libraries not available")
    
    resp = supabase.table("summaries").select("*").eq("project_id", project_id).execute()
    return resp.data if resp.data else []

def embed_summary(content: str):
    """Generate embedding for summary content"""
    if not GEMINI_AVAILABLE:
        raise ValueError("Gemini AI not available")
    
    resp = genai.embed_content(model="embedding-001", content=content)
    return resp["embedding"]

def generate_group_title(contents: list[str]) -> str:
    """Generate a title for a group of summaries using AI"""
    if not GEMINI_AVAILABLE:
        return "Untitled Group"
    
    prompt = (
        "Generate a short, high-level title summarizing these meeting topics:\n\n"
        + "\n\n".join(contents)
    )
    resp = genai.generate_content(model="gemini-1.5-flash", prompt=prompt)
    return resp.text.strip()

def generate_context_groups(project_id: str, num_clusters: int = 5):
    """Generate context groups for a project using AI clustering"""
    if not ML_AVAILABLE:
        raise ValueError("Machine learning libraries not available. Please install scikit-learn and numpy.")
    
    if not GEMINI_AVAILABLE:
        raise ValueError("AI libraries not available. Please install google-generativeai.")
    
    summaries = fetch_project_summaries(project_id)
    if not summaries:
        return {"message": f"No summaries found for project {project_id}"}

    # Embed all summary contents
    embeddings = np.array([embed_summary(s["content"]) for s in summaries])
    kmeans = KMeans(n_clusters=num_clusters)
    clusters = kmeans.fit_predict(embeddings)

    clustered_data = {i: [] for i in range(num_clusters)}
    for idx, cluster_id in enumerate(clusters):
        clustered_data[cluster_id].append(summaries[idx])

    for cluster_id, cluster_summaries in clustered_data.items():
        contents = [s["content"] for s in cluster_summaries]
        title = generate_group_title(contents)

        context_group_id = str(uuid.uuid4())
        supabase.table("context_groups").insert(
            {"context_group_id": context_group_id, "project_id": project_id, "context_title": title}
        ).execute()

        for summary in cluster_summaries:
            supabase.table("context_group_meetings").insert(
                {
                    "context_group_id": context_group_id,
                    "meeting_id": summary["meeting_id"],
                    "meeting_title": summary.get("content")[:100],
                    "meeting_date": summary.get("created_at").split('T')[0] if summary.get("created_at") else None,
                }
            ).execute()

    return {"message": f"Context groups created for project {project_id}"}

