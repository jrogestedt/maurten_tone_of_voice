import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session, select

from .. import storage
from ..config import get_settings
from ..database import get_session
from ..deps import require_auth
from ..extract import ExtractionError, UnsupportedFileType, extract_text, is_supported
from ..models import Document
from ..schemas import DocumentCreate, DocumentRead, DocumentUpdate, DownloadResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/documents", tags=["documents"], dependencies=[Depends(require_auth)]
)


def _mirror_text_to_s3(doc: Document) -> None:
    """Store a .md copy of a pasted document's text as its S3 original.

    Best-effort: the text is already safe in the DB, so an S3 failure here is
    logged but does not fail the request (the doc just has no downloadable original).
    """
    if not storage.is_enabled():
        return
    key = storage.build_key(doc.id, f"{doc.title or 'document'}.md")
    try:
        storage.put_object(key, doc.content.encode("utf-8"), "text/markdown")
        doc.s3_key = key
        doc.mime_type = "text/markdown"
        if not doc.original_filename:
            doc.original_filename = f"{doc.title or 'document'}.md"
    except storage.StorageError as exc:
        logger.warning("S3 mirror failed for document %s: %s", doc.id, exc)


@router.get("", response_model=list[DocumentRead])
def list_documents(session: Session = Depends(get_session)) -> list[Document]:
    return session.exec(select(Document).order_by(Document.updated_at.desc())).all()


@router.post("", response_model=DocumentRead, status_code=201)
def create_document(
    payload: DocumentCreate, session: Session = Depends(get_session)
) -> Document:
    doc = Document(**payload.model_dump(), source_type="text")
    session.add(doc)
    session.commit()
    session.refresh(doc)  # need the id to build the S3 key
    _mirror_text_to_s3(doc)
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc


@router.post("/upload", response_model=DocumentRead, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    category: str = Form("general"),
    active: bool = Form(True),
    session: Session = Depends(get_session),
) -> Document:
    settings = get_settings()
    filename = file.filename or "upload"

    if not is_supported(filename):
        raise HTTPException(
            status_code=422,
            detail="Unsupported file type. Allowed: .txt, .md, .pdf, .docx, .doc",
        )

    data = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {settings.max_upload_size_mb} MB limit.",
        )
    if not data:
        raise HTTPException(status_code=422, detail="The uploaded file is empty.")

    try:
        content = extract_text(filename, data)
    except UnsupportedFileType as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    doc = Document(
        title=title,
        category=category,
        content=content,
        active=active,
        source_type="upload",
        original_filename=filename,
        mime_type=file.content_type,
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)  # need the id to build the S3 key

    # The original file is the canonical artifact — fail loudly if S3 rejects it.
    if storage.is_enabled():
        key = storage.build_key(doc.id, filename)
        try:
            storage.put_object(key, data, file.content_type)
        except storage.StorageError as exc:
            session.delete(doc)
            session.commit()
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        doc.s3_key = key
        session.add(doc)
        session.commit()
        session.refresh(doc)

    return doc


@router.get("/{doc_id}", response_model=DocumentRead)
def get_document(doc_id: int, session: Session = Depends(get_session)) -> Document:
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.get("/{doc_id}/download", response_model=DownloadResponse)
def download_document(
    doc_id: int, session: Session = Depends(get_session)
) -> DownloadResponse:
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not doc.s3_key:
        raise HTTPException(status_code=404, detail="No original file for this document")
    try:
        url = storage.presigned_get_url(doc.s3_key)
    except storage.StorageError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return DownloadResponse(url=url)


@router.put("/{doc_id}", response_model=DocumentRead)
def update_document(
    doc_id: int, payload: DocumentUpdate, session: Session = Depends(get_session)
) -> Document:
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    fields = payload.model_dump(exclude_unset=True)
    content_changed = "content" in fields and fields["content"] != doc.content
    for key, value in fields.items():
        setattr(doc, key, value)
    doc.updated_at = datetime.now(timezone.utc)
    # Re-mirror only for text docs whose content changed; an uploaded file's
    # original is immutable, so we leave its S3 object untouched.
    if content_changed and doc.source_type == "text":
        _mirror_text_to_s3(doc)
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc


@router.delete("/{doc_id}", status_code=204)
def delete_document(doc_id: int, session: Session = Depends(get_session)) -> None:
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.s3_key and storage.is_enabled():
        try:
            storage.delete_object(doc.s3_key)
        except storage.StorageError as exc:
            # Don't block deletion of the DB row on a storage hiccup.
            logger.warning("Failed to delete S3 object %s: %s", doc.s3_key, exc)
    session.delete(doc)
    session.commit()
