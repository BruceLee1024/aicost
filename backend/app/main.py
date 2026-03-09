from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.api.routes.agent_validate import router as agent_validate_router
from app.api.routes.agent_valuate import router as agent_valuate_router
from app.api.routes.ai_analyze import router as ai_analyze_router
from app.api.routes.auto_valuate import router as auto_valuate_router
from app.api.routes.ai_chat import router as ai_chat_router
from app.api.routes.ai_settings import router as ai_settings_router
from app.api.routes.ai_enhanced import router as ai_enhanced_router
from app.api.routes.auth import router as auth_router
from app.api.routes.audit_logs import router as audit_logs_router
from app.api.routes.bindings import router as bindings_router
from app.api.routes.boq_generate import router as boq_generate_router
from app.api.routes.drawing_recognition import router as drawing_recognition_router
from app.api.routes.boq_items import router as boq_items_router
from app.api.routes.calculate import router as calculate_router
from app.api.routes.collaboration import router as collaboration_router
from app.api.routes.exports import router as exports_router
from app.api.routes.health import router as health_router
from app.api.routes.imports import router as imports_router
from app.api.routes.match import router as match_router
from app.api.routes.material_prices import router as material_prices_router
from app.api.routes.measures import router as measures_router
from app.api.routes.projects import router as projects_router
from app.api.routes.provenance import router as provenance_router
from app.api.routes.query import router as query_router
from app.api.routes.rule_packages import router as rule_packages_router
from app.api.routes.snapshots import router as snapshots_router
from app.api.routes.standard_codes import router as standard_codes_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.validation import router as validation_router
from app.api.routes.valuation_management import router as valuation_management_router
from app.db.base import Base
from app.db.session import engine

# Import models so SQLAlchemy is aware of them for metadata.create_all
import app.models  # noqa: F401

app = FastAPI(title="AI Native Valuation Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _create_tables() -> None:
    # MVP/dev convenience. Replace with migrations (Alembic) later.
    Base.metadata.create_all(bind=engine)
    _migrate_dev_schema()
    _load_ai_settings_from_db()


def _load_ai_settings_from_db() -> None:
    """Restore persisted AI settings into os.environ so get_ai_settings() picks them up."""
    import os
    from app.db.session import SessionLocal
    from app.models.system_setting import SystemSetting

    db = SessionLocal()
    try:
        rows = db.query(SystemSetting).filter(SystemSetting.key.like("AI_%")).all()
        for row in rows:
            if row.value:  # only set non-empty values
                os.environ[row.key] = row.value
    except Exception:
        pass  # DB may not exist yet on first run
    finally:
        db.close()


def _migrate_dev_schema() -> None:
    """Best-effort dev migration for local DB files without Alembic."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    # --- projects: add standard_type / language / currency ---
    if "projects" in tables:
        proj_cols = {c["name"] for c in inspector.get_columns("projects")}
        with engine.begin() as conn:
            if "standard_type" not in proj_cols:
                conn.execute(text(
                    "ALTER TABLE projects ADD COLUMN standard_type VARCHAR(50) NOT NULL DEFAULT 'GB50500'"
                ))
            if "language" not in proj_cols:
                conn.execute(text(
                    "ALTER TABLE projects ADD COLUMN language VARCHAR(20) NOT NULL DEFAULT 'zh'"
                ))
            if "currency" not in proj_cols:
                conn.execute(text(
                    "ALTER TABLE projects ADD COLUMN currency VARCHAR(10) NOT NULL DEFAULT 'CNY'"
                ))

    # --- line_item_quota_bindings: add coefficient ---
    if "line_item_quota_bindings" not in tables:
        return
    columns = {c["name"] for c in inspector.get_columns("line_item_quota_bindings")}
    if "coefficient" in columns:
        return

    with engine.begin() as conn:
        dialect = conn.dialect.name
        if dialect == "sqlite":
            conn.execute(
                text(
                    "ALTER TABLE line_item_quota_bindings "
                    "ADD COLUMN coefficient FLOAT NOT NULL DEFAULT 1.0"
                )
            )
        else:
            conn.execute(
                text(
                    "ALTER TABLE line_item_quota_bindings "
                    "ADD COLUMN coefficient DOUBLE PRECISION NOT NULL DEFAULT 1.0"
                )
            )


app.include_router(health_router)
app.include_router(projects_router, prefix="/api")
app.include_router(boq_items_router, prefix="/api")
app.include_router(boq_generate_router, prefix="/api")
app.include_router(bindings_router, prefix="/api")
app.include_router(match_router, prefix="/api")
app.include_router(calculate_router, prefix="/api")
app.include_router(imports_router, prefix="/api")
app.include_router(exports_router, prefix="/api")
app.include_router(provenance_router, prefix="/api")
app.include_router(rule_packages_router, prefix="/api")
app.include_router(material_prices_router, prefix="/api")
app.include_router(snapshots_router, prefix="/api")
app.include_router(measures_router, prefix="/api")
app.include_router(collaboration_router, prefix="/api")
app.include_router(query_router, prefix="/api")
app.include_router(audit_logs_router, prefix="/api")
app.include_router(validation_router, prefix="/api")
app.include_router(valuation_management_router, prefix="/api")
app.include_router(standard_codes_router, prefix="/api")
app.include_router(ai_settings_router, prefix="/api")
app.include_router(ai_analyze_router, prefix="/api")
app.include_router(auto_valuate_router, prefix="/api")
app.include_router(ai_chat_router, prefix="/api")
app.include_router(agent_valuate_router, prefix="/api")
app.include_router(agent_validate_router, prefix="/api")
app.include_router(drawing_recognition_router, prefix="/api")
app.include_router(tasks_router, prefix="/api")
app.include_router(ai_enhanced_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
