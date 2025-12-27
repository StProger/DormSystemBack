from datetime import timedelta
from uuid import uuid4
import mimetypes
import os

from minio import Minio
from fastapi import UploadFile
from .config import get_settings

settings = get_settings()

_minio = Minio(
    settings.S3_ENDPOINT,
    access_key=settings.S3_ACCESS_KEY,
    secret_key=settings.S3_SECRET_KEY,
    secure=settings.S3_SECURE,
)

def ensure_bucket():
    if not _minio.bucket_exists(settings.S3_BUCKET):
        _minio.make_bucket(settings.S3_BUCKET)

def make_key(prefix: str, filename: str) -> str:
    ext = ""
    if "." in (filename or ""):
        ext = filename.rsplit(".", 1)[-1].lower()
        if len(ext) > 10:
            ext = ""
    return f"{prefix}/{uuid4()}" + (f".{ext}" if ext else "")

async def upload_file(prefix: str, file: UploadFile) -> tuple[str, int, str | None]:
    """
    Стриминг в MinIO без чтения в память.
    Возвращает (object_key, size_bytes, etag).
    Если размер вычислить не удалось, size_bytes=0.
    """
    ensure_bucket()
    key = make_key(prefix, file.filename or "upload.bin")

    # Попробуем получить размер через seek/tell (работает для SpooledTemporaryFile)
    f = file.file
    size = -1
    try:
        cur = f.tell()
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(0, os.SEEK_SET)
    except Exception:
        size = -1  # не удалось — пойдём length=-1

    ctype = file.content_type or (mimetypes.guess_type(file.filename or "")[0]) or "application/octet-stream"

    if size >= 0:
        # обычная передача с известной длиной (не грузим в память)
        result = _minio.put_object(
            bucket_name=settings.S3_BUCKET,
            object_name=key,
            data=f,
            length=size,
            content_type=ctype,
        )
        return key, size, getattr(result, "etag", None)
    else:
        # длина неизвестна — multipart-стриминг
        result = _minio.put_object(
            bucket_name=settings.S3_BUCKET,
            object_name=key,
            data=f,
            length=-1,
            part_size=10 * 1024 * 1024,  # 10MB
            content_type=ctype,
        )
        # размер узнать не можем надёжно — вернём 0
        return key, 0, getattr(result, "etag", None)

def presign_get(object_key: str, expire_minutes: int = 10) -> str:
    return _minio.presigned_get_object(
        settings.S3_BUCKET, object_key, expires=timedelta(minutes=expire_minutes)
    )
