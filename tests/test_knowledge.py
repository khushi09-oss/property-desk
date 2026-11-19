import pytest
from pydantic import ValidationError

from app.knowledge import Document, Knowledge


def test_project_and_platform_questions_find_their_sources():
    knowledge = Knowledge.load()
    assert knowledge.search("What amenities does DG1 have?")[0].id == "dg1"
    assert (
        knowledge.search("How do I list a property on Wasalt?")[0].publisher == "Wasalt"
    )
    assert knowledge.search("Lamborghini villas in Spain")[0].id == "tierra-viva"


def test_unsupported_and_sql_like_queries_are_safe():
    knowledge = Knowledge.load()
    assert knowledge.search("quantum entanglement") == []
    knowledge.search('" OR 1=1; DROP TABLE documents; --')
    assert knowledge.search("DG1")[0].id == "dg1"


def test_snapshot_preserves_conflicting_source_ranges():
    records = {item.id: item for item in Knowledge.load().documents}
    assert "84" in records["les-vagues"].text
    assert "86" in records["les-vagues"].text
    assert "conflict" in records["les-vagues"].text.lower()


def test_plural_pool_question_retrieves_all_three_projects():
    found = {
        doc.id for doc in Knowledge.load().search("Which projects have swimming pools?")
    }
    assert {"dg1", "les-vagues", "tierra-viva"}.issubset(found)


def test_publisher_name_is_searchable():
    found = Knowledge.load().search("Which DarGlobal projects are in the snapshot?")
    assert {"dg1", "les-vagues", "tierra-viva"}.issubset({doc.id for doc in found})


@pytest.mark.parametrize("question", ["darglobal", "DarGlobal", "Dar Global", "What is DarGlobal?"])
def test_company_queries_start_with_company_and_include_projects(question):
    found = Knowledge.load().search(question)
    assert found[0].id == "darglobal-company"
    assert {"dg1", "les-vagues", "tierra-viva"}.issubset({doc.id for doc in found})


def test_company_context_does_not_replace_specific_project_evidence():
    found = Knowledge.load().search("DarGlobal DG1 amenities")
    assert found[0].id == "darglobal-company"
    assert any(doc.id == "dg1" for doc in found)


@pytest.mark.parametrize(
    "field,value",
    [
        ("url", "https://example.com/private"),
        ("url", "http://wasalt.sa/en"),
        ("text", "Contact someone@example.com"),
        ("text", "Call +971 50 123 4567"),
    ],
)
def test_capture_validation_rejects_external_links_and_contact_data(field, value):
    record = Knowledge.load().documents[0].model_dump(mode="json")
    record[field] = value
    with pytest.raises(ValidationError):
        Document.model_validate(record)
