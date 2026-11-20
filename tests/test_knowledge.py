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


def test_plural_pool_question_matches_singular_amenities():
    # Isolate the original stemming regression from the four-result corpus limit.
    knowledge = Knowledge([
        doc for doc in Knowledge.load().documents
        if doc.id in {"dg1", "les-vagues", "tierra-viva"}
    ])
    found = {doc.id for doc in knowledge.search("Which projects have swimming pools?")}
    assert {"dg1", "les-vagues", "tierra-viva"}.issubset(found)


def test_publisher_name_is_searchable():
    found = Knowledge.load().search("Which DarGlobal projects are in the snapshot?")
    assert len(found) == 4
    assert len({doc.id for doc in found}) == 4
    assert all(doc.publisher == "DarGlobal" for doc in found)
    assert all(doc.id != "darglobal-company" for doc in found[1:])


@pytest.mark.parametrize("question", ["darglobal", "DarGlobal", "Dar Global", "What is DarGlobal?"])
def test_company_queries_start_with_company_and_include_projects(question):
    found = Knowledge.load().search(question)
    assert found[0].id == "darglobal-company"
    assert len(found) == 4
    assert len({doc.id for doc in found}) == 4
    assert all(doc.publisher == "DarGlobal" for doc in found)
    assert all(doc.id != "darglobal-company" for doc in found[1:])


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


@pytest.mark.parametrize(
    "question,expected",
    [
        ("What amenities does The Astera offer?", "the-astera"),
        ("Marea Missoni Costa del Sol", "marea"),
        ("AIDA Muscat Oman", "aida"),
        ("Urban Oasis by Missoni", "urban-oasis"),
        ("Da Vinci Pagani", "davinci-tower"),
        ("W Residences Downtown Dubai", "w-residences"),
        ("Trump Tower Jeddah", "trump-tower-jeddah"),
        ("Wasalt An-Nadheem apartment", "wasalt-riyadh-nadheem-2br"),
        ("Wasalt Al-Qadisiyah apartment", "wasalt-riyadh-qadisiyah-3br"),
        ("Wasalt Sedra villa", "wasalt-riyadh-sedra-villa"),
        ("Wasalt Al-Murooj furnished rent", "wasalt-riyadh-murooj-rent"),
        ("Wasalt Obhur Jeddah rent", "wasalt-jeddah-obhur-rent"),
        ("Wasalt Dammam Badr apartment", "wasalt-dammam-badr-5br"),
        ("Wasalt Oraid land", "wasalt-riyadh-oraid-land"),
    ],
)
def test_expanded_topics_retrieve_their_own_source(question, expected):
    assert expected in {doc.id for doc in Knowledge.load().search(question)[:2]}


def test_expanded_comparisons_keep_both_relevant_sources():
    ids = {doc.id for doc in Knowledge.load().search("Compare An-Nadheem and Al-Qadisiyah asking prices")}
    assert {"wasalt-riyadh-nadheem-2br", "wasalt-riyadh-qadisiyah-3br"} <= ids
    ids = {doc.id for doc in Knowledge.load().search("Compare Marea and Tierra Viva in Spain")}
    assert {"marea", "tierra-viva"} <= ids


def test_new_source_conflicts_and_rental_periods_are_not_silently_resolved():
    records = Knowledge.load().by_id
    assert "conflict" in records["marea"].text.lower()
    assert all(value in records["marea"].text for value in ("147", "382", "223", "553"))
    assert all(value in records["wasalt-jeddah-obhur-rent"].text for value in ("1000", "180", "conflict"))
    assert all(value in records["wasalt-riyadh-oraid-land"].text for value in ("648,000", "648,105", "conflict"))
    assert "monthly" in records["wasalt-riyadh-murooj-rent"].text
    assert "yearly" in records["wasalt-jeddah-obhur-rent"].text


def test_broad_pool_query_keeps_bounded_relevant_sources():
    found = Knowledge.load().search("Which projects have swimming pools?")
    assert len(found) == 4
    assert all(doc.publisher == "DarGlobal" and "pool" in doc.text.lower() for doc in found)


def test_snapshot_keeps_original_dates_and_new_collection_provenance():
    documents = Knowledge.load().documents
    assert len(documents) == 23
    assert len({doc.url for doc in documents}) == 22
    assert str(documents[0].collected_at) == "2026-11-19"
    assert all(str(doc.collected_at) == "2026-11-20" for doc in documents[9:])
    assert all(doc.method == "web-extraction" for doc in documents)
