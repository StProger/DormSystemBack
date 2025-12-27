from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.storage_minio import upload_file, presign_get
from app.models.user import User
from app.models.file_storage import FileStorage, StorageBackend
from app.models.announcement import Announcement
from app.schemas.announcement import AnnouncementCreate, AnnouncementOut

router = APIRouter(prefix="/announcements", tags=["announcements"])
settings = get_settings()

@router.post("", response_model=AnnouncementOut, status_code=201)
async def create_announcement(
    title: str = Form(...),
    body: str = Form(...),
    image: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    if current.role.value not in ("comendant", "head"):
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    image_file_id = None
    if image:
        key, size, etag = await upload_file("announcements", image)  # <- стриминг
        fs = FileStorage(
            bucket=settings.S3_BUCKET,
            backend=StorageBackend.s3,
            object_key=key,
            file_name=image.filename or "image",
            mime_type=image.content_type or "application/octet-stream",
            size_bytes=size if size is not None else 0,  # NOT NULL
            etag=etag,
            uploaded_by=current.id,
            uploaded_at="now()",
        )
        db.add(fs)
        await db.flush()
        image_file_id = fs.id

    ann = Announcement(title=title, body=body, created_by=current.id, image_file_id=image_file_id)
    db.add(ann)
    await db.commit()
    await db.refresh(ann)

    image_url = None
    if image_file_id:
        res = await db.execute(select(FileStorage).where(FileStorage.id == image_file_id))
        f = res.scalar_one_or_none()
        if f:
            image_url = presign_get(f.object_key)

    return AnnouncementOut(
        id=str(ann.id),
        title=ann.title,
        body=ann.body,
        image_url=image_url,
        publish_at=ann.publish_at,
    )

@router.get("", response_model=list[AnnouncementOut])
async def list_announcements(
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    res = await db.execute(select(Announcement).order_by(Announcement.publish_at.desc()))
    anns = res.scalars().all()

    file_ids = [a.image_file_id for a in anns if a.image_file_id]
    files_map = {}
    if file_ids:
        res2 = await db.execute(select(FileStorage).where(FileStorage.id.in_(file_ids)))
        for f in res2.scalars():
            files_map[str(f.id)] = f

    out: list[AnnouncementOut] = []
    for a in anns:
        url = None
        if a.image_file_id and str(a.image_file_id) in files_map:
            url = presign_get(files_map[str(a.image_file_id)].object_key)
        out.append(AnnouncementOut(
            id=str(a.id),
            title=a.title,
            body=a.body,
            image_url=url,
            publish_at=a.publish_at,
        ))
    return out
