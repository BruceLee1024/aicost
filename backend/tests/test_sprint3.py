"""Sprint 3 integration tests: snapshots, diff comparison, incremental recalc.

DB fixtures provided by conftest.py.
"""

from app.models.boq_item import BoqItem
from app.models.line_item_quota_binding import LineItemQuotaBinding
from app.models.quota_item import QuotaItem


def _seed(db, project_id):
    """Seed BOQ + quota items with bindings, return (boq1, boq2, q1, q2)."""
    boq1 = BoqItem(project_id=project_id, code="010101", name="混凝土浇筑C30", unit="m3", quantity=100)
    boq2 = BoqItem(project_id=project_id, code="010201", name="钢筋制安", unit="t", quantity=5)
    q1 = QuotaItem(quota_code="D-C30", name="混凝土浇筑C30", unit="m3",
                   labor_qty=2.0, material_qty=5.0, machine_qty=1.0)
    q2 = QuotaItem(quota_code="D-RB01", name="钢筋制作安装", unit="t",
                   labor_qty=10.0, material_qty=1.0, machine_qty=0.5)
    db.add_all([boq1, boq2, q1, q2])
    db.commit()
    db.refresh(boq1)
    db.refresh(boq2)
    db.refresh(q1)
    db.refresh(q2)
    # Create bindings
    db.add(LineItemQuotaBinding(boq_item_id=boq1.id, quota_item_id=q1.id))
    db.add(LineItemQuotaBinding(boq_item_id=boq2.id, quota_item_id=q2.id))
    db.commit()
    return boq1, boq2, q1, q2


# ---------------------------------------------------------------------------
# Snapshot CRUD
# ---------------------------------------------------------------------------

def test_create_snapshot(client, db):
    r = client.post("/api/projects", json={"name": "Snap", "region": "bj"})
    pid = r.json()["id"]
    _seed(db, pid)

    r = client.post(f"/api/projects/{pid}/snapshots", json={"label": "v1"})
    assert r.status_code == 200
    snap = r.json()
    assert snap["label"] == "v1"
    assert snap["grand_total"] > 0
    assert snap["project_id"] == pid


def test_list_snapshots(client, db):
    r = client.post("/api/projects", json={"name": "ListSnap", "region": "sh"})
    pid = r.json()["id"]
    _seed(db, pid)

    client.post(f"/api/projects/{pid}/snapshots", json={"label": "v1"})
    client.post(f"/api/projects/{pid}/snapshots", json={"label": "v2"})

    r = client.get(f"/api/projects/{pid}/snapshots")
    assert r.status_code == 200
    snaps = r.json()
    assert len(snaps) == 2
    # Most recent first
    assert snaps[0]["label"] == "v2"


def test_get_snapshot_detail(client, db):
    r = client.post("/api/projects", json={"name": "Detail", "region": "gd"})
    pid = r.json()["id"]
    _seed(db, pid)

    r = client.post(f"/api/projects/{pid}/snapshots", json={"label": "detail"})
    snap_id = r.json()["id"]

    r = client.get(f"/api/snapshots/{snap_id}")
    assert r.status_code == 200
    assert r.json()["id"] == snap_id


def test_get_snapshot_404(client):
    r = client.get("/api/snapshots/99999")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Diff comparison
# ---------------------------------------------------------------------------

def test_diff_unchanged(client, db):
    """Two snapshots with identical data should show no changes."""
    r = client.post("/api/projects", json={"name": "DiffSame", "region": "bj"})
    pid = r.json()["id"]
    _seed(db, pid)

    r1 = client.post(f"/api/projects/{pid}/snapshots", json={"label": "v1"})
    r2 = client.post(f"/api/projects/{pid}/snapshots", json={"label": "v2"})
    sid1 = r1.json()["id"]
    sid2 = r2.json()["id"]

    r = client.post(f"/api/projects/{pid}/diff", json={
        "snapshot_a_id": sid1,
        "snapshot_b_id": sid2,
    })
    assert r.status_code == 200
    diff = r.json()
    assert diff["grand_total_delta"] == 0
    assert all(line["change_type"] == "unchanged" for line in diff["lines"])


def test_diff_after_quantity_change(client, db):
    """Changing quantity between snapshots should show a modified line."""
    r = client.post("/api/projects", json={"name": "DiffChg", "region": "sh"})
    pid = r.json()["id"]
    boq1, boq2, q1, q2 = _seed(db, pid)

    # Snapshot v1
    r1 = client.post(f"/api/projects/{pid}/snapshots", json={"label": "v1"})
    sid1 = r1.json()["id"]
    old_total = r1.json()["grand_total"]

    # Change quantity of boq1
    boq1.quantity = 200
    boq1.is_dirty = 1
    db.commit()

    # Snapshot v2
    r2 = client.post(f"/api/projects/{pid}/snapshots", json={"label": "v2"})
    sid2 = r2.json()["id"]
    new_total = r2.json()["grand_total"]

    assert new_total > old_total

    r = client.post(f"/api/projects/{pid}/diff", json={
        "snapshot_a_id": sid1,
        "snapshot_b_id": sid2,
    })
    diff = r.json()
    assert diff["grand_total_delta"] > 0
    modified = [l for l in diff["lines"] if l["change_type"] == "modified"]
    assert len(modified) >= 1


def test_diff_snapshot_not_found(client, db):
    r = client.post("/api/projects", json={"name": "D404", "region": "bj"})
    pid = r.json()["id"]
    r = client.post(f"/api/projects/{pid}/diff", json={
        "snapshot_a_id": 888, "snapshot_b_id": 999,
    })
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Incremental recalculation
# ---------------------------------------------------------------------------

def test_incremental_recalc_dirty_flag(client, db):
    """After calculation, dirty flags should be cleared."""
    r = client.post("/api/projects", json={"name": "Incr", "region": "bj"})
    pid = r.json()["id"]
    boq1, boq2, q1, q2 = _seed(db, pid)

    # All items start dirty
    assert boq1.is_dirty == 1

    # Run full calculation
    client.post(f"/api/projects/{pid}/snapshots", json={"label": "v1"})

    db.refresh(boq1)
    db.refresh(boq2)
    assert boq1.is_dirty == 0
    assert boq2.is_dirty == 0


def test_binding_sets_dirty(client, db):
    """Creating a binding should mark the BOQ item as dirty."""
    r = client.post("/api/projects", json={"name": "Dirty", "region": "sh"})
    pid = r.json()["id"]

    boq = BoqItem(project_id=pid, code="D01", name="Item", unit="m", quantity=10, is_dirty=0)
    q = QuotaItem(quota_code="Q-D01", name="Item", unit="m",
                  labor_qty=1, material_qty=1, machine_qty=1)
    db.add_all([boq, q])
    db.commit()
    db.refresh(boq)
    db.refresh(q)

    assert boq.is_dirty == 0

    # Confirm binding via API
    r = client.post(f"/api/boq-items/{boq.id}/quota-binding:confirm",
                    json={"quota_item_id": q.id})
    assert r.status_code == 200

    db.refresh(boq)
    assert boq.is_dirty == 1
