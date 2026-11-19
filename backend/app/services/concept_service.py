"""سرویس گراف مفاهیم (بخش ۳.۲)."""
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.errors import validation_error
from app.models.concepts import Concept, ConceptMisconception, ConceptRelation, TopicConcept
from app.models.syllabus import SyllabusTopic


def create_concept(db: Session, course_id, user, key: str, name: str,
                   description: str | None = None, topic_ids: list | None = None,
                   prerequisite_ids: list | None = None,
                   misconceptions: list[dict] | None = None,
                   examples: str | None = None, counter_examples: str | None = None,
                   status: str = "DRAFT") -> Concept:
    if not re_key(key):
        raise validation_error("شناسه مفهوم باید حروف/عدد/خط تیره انگلیسی باشد")
    exists = db.query(Concept).filter(Concept.course_id == course_id, Concept.key == key).first()
    if exists:
        raise validation_error(f"شناسه مفهوم «{key}» در این درس تکراری است")
    concept = Concept(
        course_id=course_id, key=key, name=name, description=description,
        examples=examples, counter_examples=counter_examples, status=status,
        created_by=user.id, approved_by=user.id if status == "APPROVED" else None,
    )
    db.add(concept)
    db.flush()
    for tid in topic_ids or []:
        db.add(TopicConcept(topic_id=tid, concept_id=concept.id))
    for pid in prerequisite_ids or []:
        db.add(ConceptRelation(from_concept_id=pid, to_concept_id=concept.id,
                               rel_type="PREREQUISITE_OF", created_by=user.id))
    for mc in misconceptions or []:
        db.add(ConceptMisconception(
            concept_id=concept.id,
            title=mc.get("title", "بدفهمی بدون عنوان"),
            description=mc.get("description"),
            correction_hint=mc.get("correction_hint"),
        ))
    audit(db, user.id, "CONCEPT_CREATE", "concept", concept.id, after={"key": key})
    db.flush()
    return concept


def re_key(key: str) -> bool:
    import re as _re
    return bool(_re.match(r"^[a-zA-Z][a-zA-Z0-9_\-]{1,60}$", key))


def add_relation(db: Session, user, from_concept: Concept, to_concept: Concept, rel_type: str) -> ConceptRelation:
    if rel_type not in ("PREREQUISITE_OF", "PART_OF", "RELATED_TO", "APPLIED_IN", "MISCONCEPTION_OF"):
        raise validation_error("نوع رابط نامعتبر است")
    if from_concept.course_id != to_concept.course_id:
        raise validation_error("روابط مفاهیم بین دو درس مجاز نیست")
    rel = ConceptRelation(from_concept_id=from_concept.id, to_concept_id=to_concept.id,
                          rel_type=rel_type, created_by=user.id)
    db.add(rel)
    db.flush()
    return rel


def get_prerequisites(db: Session, concept_id) -> list[Concept]:
    rows = (
        db.query(ConceptRelation)
        .filter(ConceptRelation.to_concept_id == concept_id,
                ConceptRelation.rel_type == "PREREQUISITE_OF")
        .all()
    )
    return [db.get(Concept, r.from_concept_id) for r in rows]


def concept_graph(db: Session, course_id) -> dict:
    """گراف کامل مفاهیم درس — نمایش نقشه مفاهیم با وضعیت «نامشخص» در نبود شواهد."""
    concepts = db.query(Concept).filter(Concept.course_id == course_id).order_by(Concept.name).all()
    relations = (
        db.query(ConceptRelation)
        .join(Concept, ConceptRelation.from_concept_id == Concept.id)
        .filter(Concept.course_id == course_id)
        .all()
    )
    topic_maps = (
        db.query(TopicConcept, SyllabusTopic)
        .join(Concept, TopicConcept.concept_id == Concept.id)
        .join(SyllabusTopic, TopicConcept.topic_id == SyllabusTopic.id)
        .filter(Concept.course_id == course_id)
        .all()
    )
    topic_by_concept: dict = {}
    for tc, topic in topic_maps:
        topic_by_concept.setdefault(tc.concept_id, []).append({
            "id": str(topic.id), "title": topic.title,
        })
    return {
        "nodes": [
            {
                "id": str(c.id), "key": c.key, "name": c.name,
                "description": c.description, "status": c.status,
                "topics": topic_by_concept.get(c.id, []),
            }
            for c in concepts
        ],
        "edges": [
            {"from": str(r.from_concept_id), "to": str(r.to_concept_id), "type": r.rel_type}
            for r in relations
        ],
    }
