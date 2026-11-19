"""خط RAG: قطعه‌بندی، بردار‌سازی و بازیابی مجاز (بخش ۱۴.۱).

- قطعه‌بندی RAG برای بازیابی است و از قطعه‌بندی آموزشی تدریس جدا طراحی شده است.
- منابع امتحان فعال/کلید سؤال (contains_exam_material) از مخزن گفتگو کنار گذاشته
  می‌شوند — پیش از بازیابی مجوز اعمال می‌شود (AC-09).
- MVP: بردار با روش هش‌محور قطعی ۱۲۸-بعدی و شباهت کسینوسی در حافظه؛ در استقرار
  نهایی pgvector جایگزین می‌شود.
"""
import hashlib
import math
import re

from sqlalchemy.orm import Session

EMBED_DIM = 128
_TOKEN_RE = re.compile(r"[\w\u0600-\u06FF]+")
_STOP = {"و", "در", "به", "از", "که", "این", "با", "برای", "است", "را", "های", "می", "بر"}


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text) if t not in _STOP and len(t) > 1]


def embed_text(text: str) -> list[float]:
    """بردار قطعی مبتنی بر هش — جایگزین مدل embedding در دمو."""
    vec = [0.0] * EMBED_DIM
    for tok in tokenize(text):
        h = hashlib.blake2b(tok.encode("utf-8"), digest_size=8).digest()
        idx = int.from_bytes(h[:4], "big") % EMBED_DIM
        sign = 1.0 if h[4] % 2 == 0 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [round(v / norm, 6) for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def chunk_text(text: str, target_chars: int = 600) -> list[str]:
    """قطعه‌بندی معنایی ساده: پاراگراف‌ها تا حد مجاز ادغام می‌شوند."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n|\r\n\r\n", text) if p.strip()]
    if not paragraphs:
        paragraphs = [s.strip() for s in re.split(r"(?<=[.؟!])\s+", text) if s.strip()]
    chunks: list[str] = []
    buf = ""
    for p in paragraphs:
        if buf and len(buf) + len(p) > target_chars:
            chunks.append(buf)
            buf = p
        else:
            buf = (buf + "\n" + p).strip()
    if buf:
        chunks.append(buf)
    return chunks or ([text[:target_chars]] if text else [])


def index_resource_text(db: Session, resource, text: str) -> int:
    """ساخت قطعه‌ها و بردارها برای یک منبع متنی."""
    from app.models.resources import ResourceChunk

    db.query(ResourceChunk).filter(ResourceChunk.resource_id == resource.id).delete()
    count = 0
    for i, ch in enumerate(chunk_text(text)):
        db.add(ResourceChunk(
            resource_id=resource.id,
            ordinal=i,
            text=ch,
            embedding=embed_text(ch),
            tokens=len(tokenize(ch)),
        ))
        count += 1
    db.flush()
    return count


def extract_file_text(file_bytes: bytes, filename: str) -> str:
    """استخراج متن از DOCX/PDF/متن ساده."""
    name = (filename or "").lower()
    try:
        if name.endswith(".docx"):
            import io

            from docx import Document

            doc = Document(io.BytesIO(file_bytes))
            parts = []
            for p in doc.paragraphs:
                if not p.text.strip():
                    continue
                prefix = ""
                style = (p.style.name or "").lower() if p.style is not None else ""
                if "heading 1" in style or "heading 2" in style:
                    prefix = "# "
                parts.append(prefix + p.text.strip())
            return "\n".join(parts)
        if name.endswith(".pdf"):
            import io

            import pdfplumber

            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception:  # noqa: BLE001
        pass
    try:
        return file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return file_bytes.decode("utf-8", errors="ignore")


def retrieve_chunks(
    db: Session,
    course_id,
    query: str,
    k: int = 6,
    include_exam_material: bool = False,
) -> list[dict]:
    """بازیابی قطعه‌های مجاز — فیلتر مجوز پیش از امتیازدهی اعمال می‌شود."""
    from app.models.resources import Resource, ResourceChunk

    q = (
        db.query(ResourceChunk, Resource)
        .join(Resource, ResourceChunk.resource_id == Resource.id)
        .filter(
            Resource.course_id == course_id,
            Resource.status == "AVAILABLE",
            Resource.ai_usable == True,  # noqa: E712
        )
    )
    if not include_exam_material:
        q = q.filter(Resource.contains_exam_material == False)  # noqa: E712
    qvec = embed_text(query)
    scored = []
    for chunk, res in q.all():
        if chunk.embedding:
            scored.append((cosine(qvec, chunk.embedding), chunk, res))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [
        {
            "chunk_id": str(c.id),
            "resource_id": str(r.id),
            "resource_title": r.title,
            "text": c.text,
            "locator": f"صفحه {c.page}" if c.page else (c.section or r.title),
            "score": round(s, 4),
        }
        for s, c, r in scored[:k]
    ]


def retrieve_published_content(db: Session, course_id, query: str, k: int = 3) -> list[dict]:
    """بلوک‌های محتوای منتشرشده به‌عنوان منبع گفتگو (سطح دوم بازیابی)."""
    from app.models.content import ContentDocument, ContentVersion

    qvec = embed_text(query)
    rows = (
        db.query(ContentVersion, ContentDocument)
        .join(ContentDocument, ContentVersion.document_id == ContentDocument.id)
        .filter(ContentDocument.course_id == course_id, ContentVersion.status == "PUBLISHED")
        .all()
    )
    scored = []
    for ver, doc in rows:
        for b in (ver.structured_content or {}).get("blocks", []):
            text = " ".join(
                str(b.get(f) or "") for f in ("title", "body", "question", "answer", "explanation")
            )
            if b.get("steps"):
                text += " " + " ".join(str(s) for s in b["steps"])
            if not text.strip():
                continue
            scored.append((cosine(qvec, embed_text(text)), {
                "chunk_id": f"block:{b.get('id')}",
                "resource_id": str(doc.id),
                "resource_title": doc.title,
                "text": text[:600],
                "locator": f"سند «{doc.title}» — {b.get('title') or b.get('type')}",
                "score": 0.0,
            }))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [item for _, item in scored[:k]]
