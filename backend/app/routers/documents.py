from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..deps import require_auth
from ..models import Document
from ..schemas import DocumentCreate, DocumentRead, DocumentUpdate

router = APIRouter(
    prefix="/api/documents", tags=["documents"], dependencies=[Depends(require_auth)]
)


@router.get("", response_model=list[DocumentRead])
def list_documents(session: Session = Depends(get_session)) -> list[Document]:
    return session.exec(select(Document).order_by(Document.updated_at.desc())).all()


@router.post("", response_model=DocumentRead, status_code=201)
def create_document(
    payload: DocumentCreate, session: Session = Depends(get_session)
) -> Document:
    doc = Document(**payload.model_dump())
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


@router.put("/{doc_id}", response_model=DocumentRead)
def update_document(
    doc_id: int, payload: DocumentUpdate, session: Session = Depends(get_session)
) -> Document:
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(doc, key, value)
    doc.updated_at = datetime.now(timezone.utc)
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc


@router.delete("/{doc_id}", status_code=204)
def delete_document(doc_id: int, session: Session = Depends(get_session)) -> None:
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    session.delete(doc)
    session.commit()
