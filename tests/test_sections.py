"""
Tests for Section-Based Content Discovery Architecture.
Validates Database CRUD, Post/Course many-to-many associations,
Admin management routes, Public section URLs, and Category filtering.
"""
import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient

import db
from app import app
from admin import admin_app


# ==============================================================================
# 1. Database Unit Tests (Mocked DB Connection)
# ==============================================================================

def test_slugify():
    from database.sections import slugify
    assert slugify("Systems & Architecture") == "systems-architecture"
    assert slugify("  Clean Code: Part 1  ") == "clean-code-part-1"
    assert slugify("") == "section"
    assert slugify("---") == "section"


def test_create_section_validation():
    from database.sections import create_section
    with pytest.raises(ValueError, match="Section name is required"):
        create_section({"name": "   "})


def test_create_and_get_section_mocked():
    sample_row = {
        "id": 1,
        "name": "Distributed Systems",
        "slug": "distributed-systems",
        "description": "Explorations into consensus and replication",
        "content_types": ["writing", "research"],
        "sort_order": 1,
        "is_published": True,
        "is_featured": True,
        "created_at": None,
        "updated_at": None
    }

    with patch("database.sections.get_connection") as mock_conn:
        mock_cur = MagicMock()
        mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = mock_cur
        mock_cur.fetchone.return_value = sample_row

        from database.sections import create_section, get_section_by_id, get_section_by_slug

        # Test Create
        created = create_section({
            "name": "Distributed Systems",
            "slug": "distributed-systems",
            "description": "Explorations into consensus and replication",
            "content_types": ["writing", "research"],
            "sort_order": 1,
            "is_published": True,
            "is_featured": True
        })
        assert created["name"] == "Distributed Systems"
        assert created["slug"] == "distributed-systems"

        # Test Get by ID
        fetched_id = get_section_by_id(1)
        assert fetched_id["id"] == 1

        # Test Get by Slug
        fetched_slug = get_section_by_slug("distributed-systems")
        assert fetched_slug["slug"] == "distributed-systems"


def test_post_sections_associations_mocked():
    with patch("database.sections.get_connection") as mock_conn:
        mock_cur = MagicMock()
        mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = mock_cur

        from database.sections import set_post_sections, get_section_ids_for_post

        # Test set post sections
        set_post_sections(10, [1, 2, 3])
        assert mock_cur.execute.called

        # Test get section ids
        mock_cur.fetchall.return_value = [{"section_id": 1}, {"section_id": 2}]
        ids = get_section_ids_for_post(10)
        assert ids == [1, 2]


def test_course_sections_associations_mocked():
    with patch("database.sections.get_connection") as mock_conn:
        mock_cur = MagicMock()
        mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = mock_cur

        from database.sections import set_course_sections, get_section_ids_for_course

        set_course_sections(5, [2, 4])
        assert mock_cur.execute.called

        mock_cur.fetchall.return_value = [{"section_id": 2}, {"section_id": 4}]
        ids = get_section_ids_for_course(5)
        assert ids == [2, 4]


# ==============================================================================
# 2. Admin Portal Route Tests
# ==============================================================================

def test_admin_list_sections(admin_client):
    with patch("db.get_all_sections_admin", return_value=[
        {
            "id": 1,
            "name": "Core Principles",
            "slug": "core-principles",
            "description": "Fundamental theory",
            "content_types": ["writing"],
            "sort_order": 1,
            "is_published": True,
            "is_featured": True,
            "post_count": 3,
            "course_count": 0
        }
    ]):
        response = admin_client.get("/sections")
        assert response.status_code == 200
        assert "Content Discovery Sections" in response.text
        assert "Core Principles" in response.text
        assert "/sections/core-principles" in response.text


def test_admin_new_section_form(admin_client):
    response = admin_client.get("/sections/new")
    assert response.status_code == 200
    assert "New Discovery Section" in response.text
    assert 'name="name"' in response.text
    assert 'name="slug"' in response.text


def test_admin_create_section_action(admin_client):
    with patch("db.create_section", return_value={"id": 2, "name": "New Theme", "slug": "new-theme"}) as mock_create:
        response = admin_client.post("/sections/new", data={
            "name": "New Theme",
            "slug": "new-theme",
            "description": "A brand new section",
            "content_types": ["writing", "research"],
            "sort_order": "5",
            "is_featured": "1",
            "is_published": "1"
        }, follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/sections"
        assert mock_create.called
        called_data = mock_create.call_args[0][0]
        assert called_data["name"] == "New Theme"
        assert called_data["slug"] == "new-theme"
        assert called_data["is_featured"] is True
        assert called_data["is_published"] is True
        assert called_data["sort_order"] == 5


def test_admin_edit_section_form(admin_client):
    sample_section = {
        "id": 1,
        "name": "Core Principles",
        "slug": "core-principles",
        "description": "Fundamental theory",
        "content_types": ["writing"],
        "sort_order": 1,
        "is_published": True,
        "is_featured": True
    }
    with patch("db.get_section_by_id", return_value=sample_section):
        response = admin_client.get("/sections/1/edit")
        assert response.status_code == 200
        assert "Edit Section" in response.text
        assert "Core Principles" in response.text


def test_admin_update_section_action(admin_client):
    sample_section = {
        "id": 1,
        "name": "Core Principles",
        "slug": "core-principles",
        "description": "Fundamental theory",
        "content_types": ["writing"],
        "sort_order": 1,
        "is_published": True,
        "is_featured": True
    }
    with patch("db.get_section_by_id", return_value=sample_section):
        with patch("db.update_section", return_value=sample_section) as mock_update:
            response = admin_client.post("/sections/1/edit", data={
                "name": "Core Principles Updated",
                "slug": "core-principles",
                "description": "Updated theory description",
                "content_types": ["writing", "books"],
                "sort_order": "2",
                "is_featured": "1",
                "is_published": "1"
            }, follow_redirects=False)

            assert response.status_code == 303
            assert response.headers["location"] == "/sections"
            assert mock_update.called


def test_admin_toggle_section_publish(admin_client):
    with patch("db.toggle_section_publish") as mock_toggle:
        response = admin_client.post("/sections/1/toggle-publish", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/sections"
        assert mock_toggle.called


def test_admin_delete_section(admin_client):
    with patch("db.delete_section") as mock_del:
        response = admin_client.post("/sections/1/delete", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/sections"
        assert mock_del.called


def test_admin_reorder_sections(admin_client):
    with patch("db.reorder_sections") as mock_reorder:
        response = admin_client.post("/sections/reorder", json={"ordered_ids": [3, 1, 2]})
        assert response.status_code == 200
        assert response.json() == {"success": True}
        mock_reorder.assert_called_once_with([3, 1, 2])


# ==============================================================================
# 3. Public Website Discovery & Filtering Tests
# ==============================================================================

def test_public_category_with_sections(client):
    mock_posts = [
        {
            "id": 1,
            "title": "On Distributed Raft",
            "slug": "on-distributed-raft",
            "type": "writing",
            "excerpt": "A deep dive into consensus",
            "content_markdown": "Full text here...",
            "published_at": None,
            "created_at": None,
            "tags": ["distributed"],
            "featured_image_url": None,
            "featured_image_alt": None,
            "featured_image_width": None,
            "featured_image_height": None
        }
    ]
    mock_featured = [
        {"id": 1, "name": "Consensus", "slug": "consensus", "is_featured": True, "description": "Consensus protocols"}
    ]
    mock_all_sections = [
        {"id": 1, "name": "Consensus", "slug": "consensus", "is_featured": True, "description": "Consensus protocols"},
        {"id": 2, "name": "State Machines", "slug": "state-machines", "is_featured": False, "description": "Replicated logs"}
    ]

    with patch("db.get_published_posts", return_value=mock_posts):
        with patch("db.get_featured_sections_for_type", return_value=mock_featured):
            with patch("db.get_sections_for_type", return_value=mock_all_sections):
                response = client.get("/writing")
                assert response.status_code == 200
                assert "On Distributed Raft" in response.text
                assert "Consensus" in response.text
                assert "/writing/section/consensus" in response.text


def test_public_category_direct_section_url(client):
    mock_section = {
        "id": 1,
        "name": "Consensus",
        "slug": "consensus",
        "description": "Consensus protocols and fault tolerance",
        "is_published": True
    }
    mock_posts = [
        {
            "id": 1,
            "title": "On Distributed Raft",
            "slug": "on-distributed-raft",
            "type": "writing",
            "excerpt": "A deep dive into consensus",
            "content_markdown": "Full text here...",
            "published_at": None,
            "created_at": None,
            "tags": ["distributed"],
            "featured_image_url": None,
            "featured_image_alt": None,
            "featured_image_width": None,
            "featured_image_height": None
        }
    ]

    with patch("db.get_section_by_slug", return_value=mock_section):
        with patch("db.get_published_posts", return_value=mock_posts) as mock_get_posts:
            with patch("db.get_featured_sections_for_type", return_value=[mock_section]):
                with patch("db.get_sections_for_type", return_value=[mock_section]):
                    response = client.get("/writing/section/consensus")
                    assert response.status_code == 200
                    assert "On Distributed Raft" in response.text
                    assert "Filtering by" in response.text
                    assert "Consensus" in response.text
                    # Verify db.get_published_posts was called with section_slug="consensus"
                    mock_get_posts.assert_called_with(post_type="writing", section_slug="consensus", limit=50)


def test_public_sections_explorer(client):
    mock_sections = [
        {
            "id": 1,
            "name": "Systems Architecture",
            "slug": "systems-architecture",
            "description": "High-throughput engines",
            "content_types": ["writing", "research"],
            "sort_order": 1,
            "is_published": True,
            "is_featured": True,
            "post_count": 5,
            "course_count": 1
        }
    ]
    with patch("db.get_all_sections_admin", return_value=mock_sections):
        response = client.get("/sections")
        assert response.status_code == 200
        assert "Thematic Sections" in response.text
        assert "Systems Architecture" in response.text
        assert "/sections/systems-architecture" in response.text


def test_public_section_detail_archive(client):
    mock_section = {
        "id": 1,
        "name": "Systems Architecture",
        "slug": "systems-architecture",
        "description": "High-throughput engines and foundational designs",
        "is_published": True
    }
    mock_posts = [
        {
            "id": 1,
            "title": "Scalable Storage",
            "slug": "scalable-storage",
            "type": "research",
            "excerpt": "Explorations in log structured storage",
            "content_markdown": "Full text...",
            "published_at": None,
            "created_at": None,
            "tags": ["storage"],
            "featured_image_url": None,
            "featured_image_alt": None,
            "featured_image_width": None,
            "featured_image_height": None
        }
    ]

    with patch("db.get_section_by_slug", return_value=mock_section):
        with patch("db.get_published_posts", return_value=mock_posts):
            with patch("db.get_published_courses", return_value=[]):
                response = client.get("/sections/systems-architecture")
                assert response.status_code == 200
                assert "Systems Architecture" in response.text
                assert "Scalable Storage" in response.text
                assert "/research/scalable-storage" in response.text
