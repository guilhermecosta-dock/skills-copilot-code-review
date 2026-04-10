"""
Announcement endpoints for the High School Management System API
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional, List
from datetime import date, datetime
from bson import ObjectId

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


def serialize_announcement(doc: dict) -> Dict[str, Any]:
    """Convert MongoDB document to JSON-serializable dict"""
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def get_active_announcements() -> List[Dict[str, Any]]:
    """
    Get all currently active announcements (public).

    An announcement is active when:
    - Its expiration_date is today or in the future
    - Its start_date is null or today or in the past
    """
    today = date.today().isoformat()

    query = {
        "expiration_date": {"$gte": today},
        "$or": [
            {"start_date": None},
            {"start_date": {"$lte": today}}
        ]
    }

    announcements = []
    for doc in announcements_collection.find(query).sort("created_at", -1):
        announcements.append(serialize_announcement(doc))

    return announcements


@router.get("/all", response_model=List[Dict[str, Any]])
def get_all_announcements(teacher_username: str = Query(...)) -> List[Dict[str, Any]]:
    """Get all announcements including expired ones - requires teacher authentication"""
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Authentication required")

    today = date.today().isoformat()
    announcements = []
    for doc in announcements_collection.find().sort("expiration_date", -1):
        entry = serialize_announcement(doc)
        entry["is_active"] = (
            entry["expiration_date"] >= today and
            (entry.get("start_date") is None or entry["start_date"] <= today)
        )
        announcements.append(entry)

    return announcements


@router.post("", response_model=Dict[str, Any])
def create_announcement(
    message: str,
    expiration_date: str,
    teacher_username: str = Query(...),
    start_date: Optional[str] = None
) -> Dict[str, Any]:
    """Create a new announcement - requires teacher authentication"""
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        date.fromisoformat(expiration_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid expiration_date format. Use YYYY-MM-DD.")

    if start_date:
        try:
            date.fromisoformat(start_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD.")

    if start_date and start_date > expiration_date:
        raise HTTPException(status_code=400, detail="start_date must be before expiration_date")

    doc = {
        "message": message,
        "start_date": start_date if start_date else None,
        "expiration_date": expiration_date,
        "created_at": datetime.utcnow().isoformat(),
        "created_by": teacher_username
    }

    result = announcements_collection.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc.pop("_id", None)

    return doc


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str,
    message: str,
    expiration_date: str,
    teacher_username: str = Query(...),
    start_date: Optional[str] = None
) -> Dict[str, Any]:
    """Update an existing announcement - requires teacher authentication"""
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        obj_id = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")

    try:
        date.fromisoformat(expiration_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid expiration_date format. Use YYYY-MM-DD.")

    if start_date:
        try:
            date.fromisoformat(start_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD.")

    if start_date and start_date > expiration_date:
        raise HTTPException(status_code=400, detail="start_date must be before expiration_date")

    update_data = {
        "message": message,
        "start_date": start_date if start_date else None,
        "expiration_date": expiration_date,
    }

    result = announcements_collection.update_one(
        {"_id": obj_id},
        {"$set": update_data}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    doc = announcements_collection.find_one({"_id": obj_id})
    return serialize_announcement(doc)


@router.delete("/{announcement_id}", response_model=Dict[str, Any])
def delete_announcement(
    announcement_id: str,
    teacher_username: str = Query(...)
) -> Dict[str, Any]:
    """Delete an announcement - requires teacher authentication"""
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        obj_id = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")

    result = announcements_collection.delete_one({"_id": obj_id})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return {"message": "Announcement deleted successfully"}
