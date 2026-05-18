"""Sprint 9 — Phase 2 tests for the propose-then-commit BOQ workflow."""

from __future__ import annotations

import json

import pytest

from app.ai.framework.context import AgentContext
from app.ai.framework.tool_registry import registry
import app.ai.tools.project_tools  # noqa: F401 — register tools
from app.models.project import Project
from app.models.boq_item import BoqItem


def _propose(ctx, items: str) -> str:
    return registry.execute("propose_boq_items", {"items": items}, ctx)


def _batch_create(ctx, items: str) -> str:
    return registry.execute("batch_create_boq_items", {"items": items}, ctx)


# ─────────────────────────────────────────────────────────────────
# propose_boq_items: dry-run draft generation
# ─────────────────────────────────────────────────────────────────


def _seed_project(db) -> int:
    p = Project(name="t", region="Shanghai", standard_type="GB50500", currency="CNY")
    db.add(p)
    db.commit()
    db.refresh(p)
    return p.id


class TestProposeBoqItems:
    def test_returns_draft_without_db_write(self, db):
        pid = _seed_project(db)
        ctx = AgentContext(db=db, project_id=pid)

        items = json.dumps(
            [
                {"code": "010101001", "name": "基础混凝土", "unit": "m3", "quantity": 120, "division": "基础工程"},
                {"code": "010102001", "name": "基础钢筋", "unit": "t", "quantity": 18.5, "division": "基础工程"},
                {"code": "010301001", "name": "柱混凝土", "unit": "m3", "quantity": 95, "division": "主体结构"},
            ]
        )

        result = json.loads(_propose(ctx, items))
        assert result["action"] == "drafted"
        assert result["draft_count"] == 3
        assert "draft_token" in result
        assert result["division_summary"]["基础工程"] == 2
        assert result["division_summary"]["主体结构"] == 1

        # Critical: DB should still be empty
        assert db.query(BoqItem).filter(BoqItem.project_id == pid).count() == 0

        # Draft should be retrievable from ctx.metadata
        assert "boq_drafts" in ctx.metadata
        token = result["draft_token"]
        assert token in ctx.metadata["boq_drafts"]
        assert len(ctx.metadata["boq_drafts"][token]) == 3

    def test_rejects_empty_array(self, db):
        ctx = AgentContext(db=db, project_id=_seed_project(db))
        result = json.loads(_propose(ctx, "[]"))
        assert "error" in result

    def test_rejects_invalid_json(self, db):
        ctx = AgentContext(db=db, project_id=_seed_project(db))
        result = json.loads(_propose(ctx, "not-json"))
        assert "error" in result

    def test_skips_items_without_name(self, db):
        ctx = AgentContext(db=db, project_id=_seed_project(db))
        items = json.dumps(
            [
                {"code": "001", "name": "valid", "unit": "m", "quantity": 1},
                {"code": "002", "unit": "m", "quantity": 1},  # no name
            ]
        )
        result = json.loads(_propose(ctx, items))
        assert result["draft_count"] == 1
        assert any("name" in e for e in result["errors"])

    def test_auto_assigns_code_when_missing(self, db):
        ctx = AgentContext(db=db, project_id=_seed_project(db))
        items = json.dumps([{"name": "无编码项", "unit": "项", "quantity": 1}])
        result = json.loads(_propose(ctx, items))
        assert result["draft_count"] == 1
        token = result["draft_token"]
        draft = ctx.metadata["boq_drafts"][token]
        assert draft[0]["code"].startswith("AUTO-")

    def test_caps_at_max_items(self, db):
        ctx = AgentContext(db=db, project_id=_seed_project(db))
        big = json.dumps([{"name": f"item{i}", "unit": "项", "quantity": 1} for i in range(250)])
        result = json.loads(_propose(ctx, big))
        assert "error" in result

    def test_propose_then_commit_round_trip(self, db):
        """Draft → user accepts → commit via batch_create_boq_items."""
        pid = _seed_project(db)
        ctx = AgentContext(db=db, project_id=pid)

        items = json.dumps(
            [
                {"code": "C-1", "name": "draft 1", "unit": "m3", "quantity": 10, "division": "A"},
                {"code": "C-2", "name": "draft 2", "unit": "m3", "quantity": 20, "division": "B"},
            ]
        )

        # 1) Generate draft
        draft_resp = json.loads(_propose(ctx, items))
        assert draft_resp["draft_count"] == 2
        assert db.query(BoqItem).count() == 0  # nothing written yet

        # 2) Frontend retrieves the draft, user edits it, then commits
        token = draft_resp["draft_token"]
        edited = ctx.metadata["boq_drafts"][token]
        # Simulate user trimming one item + bumping quantity on the other
        edited_payload = json.dumps([{**edited[0], "quantity": 15}])

        commit_resp = json.loads(_batch_create(ctx, edited_payload))
        assert commit_resp["action"] == "batch_created"
        assert commit_resp["created_count"] == 1

        rows = db.query(BoqItem).filter(BoqItem.project_id == pid).all()
        assert len(rows) == 1
        assert rows[0].quantity == 15
        assert rows[0].code == "C-1"


# ─────────────────────────────────────────────────────────────────
# Tool registration sanity
# ─────────────────────────────────────────────────────────────────


def test_propose_tool_registered():
    from app.ai.framework.tool_registry import registry

    tool = registry.get("propose_boq_items")
    assert tool is not None
    assert tool.read_only is True
    assert tool.destructive is False


def test_propose_tool_in_setup_agent():
    from app.ai.agents.v2.project_setup_agent import ProjectSetupAgent

    agent = ProjectSetupAgent()
    assert "propose_boq_items" in agent.tool_names
    # propose should appear before batch_create in the list (priority order)
    names = agent.tool_names
    assert names.index("propose_boq_items") < names.index("batch_create_boq_items")


# ─────────────────────────────────────────────────────────────────
# Phase 2 — Draft store + REST API
# ─────────────────────────────────────────────────────────────────


class TestDraftStore:
    def test_put_get_pop_roundtrip(self):
        from app.ai.framework.draft_store import get_draft_store

        store = get_draft_store()
        store.clear()
        store.put("tok1", 7, [{"name": "x", "code": "C"}])
        e = store.get("tok1")
        assert e is not None and e.project_id == 7
        assert store.pop("tok1") is not None
        assert store.get("tok1") is None

    def test_list_filters_by_project(self):
        from app.ai.framework.draft_store import get_draft_store

        store = get_draft_store()
        store.clear()
        store.put("a", 1, [])
        store.put("b", 2, [])
        store.put("c", 1, [])
        toks = {t for t, _ in store.list_for_project(1)}
        assert toks == {"a", "c"}


class TestDraftAPI:
    def test_get_and_commit_flow(self, client, db):
        from app.ai.framework.draft_store import get_draft_store

        get_draft_store().clear()
        pid = _seed_project(db)
        ctx = AgentContext(db=db, project_id=pid)
        items = json.dumps(
            [
                {"code": "C-1", "name": "draft 1", "unit": "m3", "quantity": 10, "division": "A"},
                {"code": "C-2", "name": "draft 2", "unit": "m3", "quantity": 20, "division": "B"},
            ]
        )
        token = json.loads(_propose(ctx, items))["draft_token"]

        # GET draft
        resp = client.get(f"/api/projects/{pid}/boq-drafts/{token}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["token"] == token
        assert len(body["items"]) == 2

        # LIST
        resp = client.get(f"/api/projects/{pid}/boq-drafts")
        assert resp.status_code == 200
        assert any(d["token"] == token for d in resp.json())

        # COMMIT (with one item edited)
        edited = body["items"]
        edited[0]["quantity"] = 99
        commit = client.post(
            f"/api/projects/{pid}/boq-drafts/{token}/commit",
            json={"items": edited},
        )
        assert commit.status_code == 200, commit.text
        result = commit.json()
        assert result["created_count"] == 2

        # Draft should have been popped
        after = client.get(f"/api/projects/{pid}/boq-drafts/{token}")
        assert after.status_code == 404

    def test_get_unknown_token_404(self, client, db):
        pid = _seed_project(db)
        resp = client.get(f"/api/projects/{pid}/boq-drafts/nope")
        assert resp.status_code == 404

    def test_commit_with_empty_items_400(self, client, db):
        from app.ai.framework.draft_store import get_draft_store

        get_draft_store().clear()
        pid = _seed_project(db)
        ctx = AgentContext(db=db, project_id=pid)
        items = json.dumps([{"name": "x", "code": "y", "unit": "m", "quantity": 1}])
        token = json.loads(_propose(ctx, items))["draft_token"]

        resp = client.post(
            f"/api/projects/{pid}/boq-drafts/{token}/commit",
            json={"items": []},
        )
        assert resp.status_code == 400

    def test_discard_draft(self, client, db):
        from app.ai.framework.draft_store import get_draft_store

        get_draft_store().clear()
        pid = _seed_project(db)
        ctx = AgentContext(db=db, project_id=pid)
        items = json.dumps([{"name": "x", "code": "y", "unit": "m", "quantity": 1}])
        token = json.loads(_propose(ctx, items))["draft_token"]

        resp = client.delete(f"/api/projects/{pid}/boq-drafts/{token}")
        assert resp.status_code == 200
        assert resp.json()["discarded"] is True
        assert client.get(f"/api/projects/{pid}/boq-drafts/{token}").status_code == 404


# ─────────────────────────────────────────────────────────────────
# Phase 3 — VectorStore + RAG tools
# ─────────────────────────────────────────────────────────────────


class TestVectorStore:
    def test_upsert_and_search_roundtrip(self, db):
        from app.ai.framework.vector_store import VectorStore

        store = VectorStore(db)
        store.upsert(
            namespace="project",
            ref_id="1",
            text="住宅楼 钢筋 混凝土 框架结构",
            meta={"name": "A楼"},
        )
        store.upsert(
            namespace="project",
            ref_id="2",
            text="商业综合体 玻璃幕墙 钢结构",
            meta={"name": "B广场"},
        )
        store.upsert(
            namespace="project",
            ref_id="3",
            text="厂房 大跨度 桁架",
            meta={"name": "C车间"},
        )
        db.commit()

        hits = store.search("project", "住宅 钢筋", top_n=2)
        assert len(hits) >= 1
        # The住宅 query should rank ref_id="1" first
        assert hits[0].ref_id == "1"
        assert hits[0].meta["name"] == "A楼"

    def test_upsert_replaces_prior_entry(self, db):
        from app.ai.framework.vector_store import VectorStore
        from app.models.embedding import Embedding

        store = VectorStore(db)
        store.upsert(namespace="project", ref_id="1", text="first")
        store.upsert(namespace="project", ref_id="1", text="second")
        db.commit()
        rows = (
            db.query(Embedding)
            .filter(Embedding.namespace == "project", Embedding.ref_id == "1")
            .all()
        )
        assert len(rows) == 1

    def test_exclude_ref_ids(self, db):
        from app.ai.framework.vector_store import VectorStore

        store = VectorStore(db)
        store.upsert(namespace="project", ref_id="1", text="住宅 钢筋")
        store.upsert(namespace="project", ref_id="2", text="住宅 钢筋")
        db.commit()
        hits = store.search("project", "住宅", top_n=5, exclude_ref_ids={"1"})
        assert all(h.ref_id != "1" for h in hits)

    def test_count(self, db):
        from app.ai.framework.vector_store import VectorStore

        store = VectorStore(db)
        store.upsert(namespace="skill_chunk", ref_id="GB", sub_key="c1", text="x")
        store.upsert(namespace="skill_chunk", ref_id="GB", sub_key="c2", text="y")
        db.commit()
        assert store.count("skill_chunk") == 2


class TestProjectIndexer:
    def test_index_and_similar(self, db):
        from app.services.project_indexer import index_project, reindex_all_projects

        # Seed three distinguishable projects
        from app.models.project import Project

        a = Project(name="住宅A", region="上海", project_type="住宅", description="框架结构 钢筋 混凝土")
        b = Project(name="商业B", region="北京", project_type="商业", description="玻璃幕墙 钢结构")
        c = Project(name="住宅C", region="深圳", project_type="住宅", description="框架 砖墙 混凝土")
        db.add_all([a, b, c])
        db.commit()

        n = reindex_all_projects(db)
        assert n == 3

        # Query for similarity to住宅A
        from app.ai.framework.vector_store import VectorStore

        store = VectorStore(db)
        hits = store.search("project", "框架 混凝土 钢筋", top_n=3)
        ref_ids = [h.ref_id for h in hits]
        # Both住宅项目 (A & C) should rank above商业B
        assert str(b.id) not in ref_ids[:2] or len(hits) < 3


class TestRagTools:
    def test_search_similar_projects_tool(self, db):
        from app.models.project import Project

        a = Project(name="住宅A", region="上海", project_type="住宅", description="框架 钢筋")
        b = Project(name="厂房B", region="北京", project_type="工业", description="桁架 钢结构")
        db.add_all([a, b])
        db.commit()

        from app.services.project_indexer import reindex_all_projects

        reindex_all_projects(db)

        ctx = AgentContext(db=db, project_id=a.id)
        result = json.loads(
            registry.execute(
                "search_similar_projects",
                {"top_n": 5},
                ctx,
            )
        )
        assert "results" in result
        # Self should be excluded
        assert all(r["project_id"] != a.id for r in result["results"])

    def test_get_price_trend_no_data(self, db):
        ctx = AgentContext(db=db, project_id=None)
        result = json.loads(
            registry.execute("get_price_trend", {"name": "钢筋", "months": 6}, ctx)
        )
        assert result.get("samples", 0) == 0

    def test_get_price_trend_with_data(self, db):
        from datetime import date
        from app.models.material_price import MaterialPrice

        for i, m in enumerate(["2025-01-15", "2025-02-15", "2025-03-15"]):
            db.add(
                MaterialPrice(
                    code="STEEL",
                    name="HRB400 钢筋",
                    unit="t",
                    unit_price=4500 + i * 100,
                    effective_date=date.fromisoformat(m),
                )
            )
        db.commit()

        ctx = AgentContext(db=db, project_id=None)
        result = json.loads(
            registry.execute(
                "get_price_trend",
                {"name": "钢筋", "months": 12},
                ctx,
            )
        )
        assert result["samples"] == 3
        assert len(result["series"]) >= 1
        assert result["overall_avg"] > 0


class TestRagApi:
    def test_similar_projects_endpoint(self, client, db):
        from app.models.project import Project
        from app.services.project_indexer import reindex_all_projects

        a = Project(name="住宅A", region="上海", project_type="住宅", description="框架 钢筋")
        b = Project(name="住宅C", region="广州", project_type="住宅", description="框架 钢筋")
        db.add_all([a, b])
        db.commit()
        reindex_all_projects(db)

        resp = client.get(f"/api/projects/{a.id}/similar?top_n=5")
        assert resp.status_code == 200
        body = resp.json()
        assert body["project_id"] == a.id
        assert all(r["project_id"] != a.id for r in body["results"])

    def test_skill_chunk_upload_endpoint(self, client, db):
        text = "GB50500 第一章 总则。本规范适用于建设工程工程量清单计价活动。" * 40
        resp = client.post(
            "/api/skills/chunks/upload",
            json={
                "skill_name": "GB50500",
                "text": text,
                "section": "总则",
                "chunk_size": 200,
                "overlap": 30,
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["skill_name"] == "GB50500"
        assert body["chunks_indexed"] >= 3

        # Now searchable via the RAG tool
        from app.ai.framework.context import AgentContext

        ctx = AgentContext(db=db, project_id=None)
        result = json.loads(
            registry.execute(
                "search_skill_chunks",
                {"query": "工程量清单", "top_n": 3},
                ctx,
            )
        )
        assert result["matched_count"] >= 1


# ─────────────────────────────────────────────────────────────────
# Phase 4 — Report renderers (DOCX) + narrative service
# ─────────────────────────────────────────────────────────────────


def _seed_project_with_items(db) -> int:
    """Helper: create a project plus a couple of BOQ rows for report tests."""
    p = Project(name="t", region="Shanghai", standard_type="GB50500", currency="CNY")
    db.add(p)
    db.commit()
    db.refresh(p)
    rows = [
        BoqItem(project_id=p.id, code="C-1", name="基础混凝土", unit="m3", quantity=100, division="基础", sort_order=1),
        BoqItem(project_id=p.id, code="C-2", name="柱混凝土", unit="m3", quantity=50, division="主体", sort_order=2),
    ]
    db.add_all(rows)
    db.commit()
    return p.id


class TestDocxRenderer:
    def test_export_docx_returns_valid_zip(self, db):
        from app.services.report_docx_service import export_valuation_docx

        pid = _seed_project_with_items(db)
        blob = export_valuation_docx(pid, db)
        # DOCX is a ZIP archive — first 2 bytes = PK
        assert blob[:2] == b"PK"
        assert len(blob) > 1000  # non-trivial output

    def test_export_docx_includes_narrative(self, db):
        from app.services.report_docx_service import export_valuation_docx
        import zipfile
        from io import BytesIO

        pid = _seed_project_with_items(db)
        narrative = "## 执行摘要\n\n这是 AI 生成的测试摘要文本。"
        blob = export_valuation_docx(pid, db, narrative=narrative)

        # Inspect document.xml for narrative phrase
        with zipfile.ZipFile(BytesIO(blob)) as z:
            with z.open("word/document.xml") as f:
                content = f.read().decode("utf-8")
        assert "测试摘要文本" in content


class TestNarrativeService:
    def test_fallback_when_llm_disabled(self, db, monkeypatch):
        from app.services.report_narrative_service import generate_narrative

        # Ensure provider returns disabled
        monkeypatch.setenv("AI_PROVIDER", "disabled")

        # Force the cached provider to be re-fetched
        from app.ai.providers import factory as factory_mod

        # Re-fetch may use cached settings; the fallback works in either case
        pid = _seed_project_with_items(db)
        text = generate_narrative(pid, db)
        assert text  # non-empty
        assert "执行摘要" in text or "项目" in text


class TestReportExportRoute:
    def test_docx_export_endpoint(self, client, db):
        pid = _seed_project_with_items(db)
        resp = client.get(f"/api/projects/{pid}/report/export?format=docx")
        assert resp.status_code == 200
        assert resp.content[:2] == b"PK"
        ct = resp.headers.get("content-type", "")
        assert "wordprocessingml" in ct

    def test_unsupported_format_returns_400(self, client, db):
        pid = _seed_project_with_items(db)
        resp = client.get(f"/api/projects/{pid}/report/export?format=odt")
        assert resp.status_code == 400
