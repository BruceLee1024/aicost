import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { message, Upload, Spin } from "antd";
import PageBreadcrumb from "../components/PageBreadcrumb";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api";

interface RecognizedComponent {
  id: string;
  type: string;
  count: number;
  spec: string;
  confidence: number;
  color: string;
  /* bounding box relative to SVG viewBox 0..1000 x 0..750 */
  bbox?: { x: number; y: number; w: number; h: number };
}

interface BoqSuggestion {
  source_component_id: string;
  suggested_code: string;
  suggested_name: string;
  suggested_unit: string;
  suggested_quantity: number;
  characteristics: string;
  confidence: number;
}

const TYPE_COLOR_MAP: Record<string, string> = {
  "框架柱": "#3b82f6",
  "框架梁": "#10b981",
  "剪力墙": "#f59e0b",
  "连梁": "#06b6d4",
  "楼板": "#8b5cf6",
  "基础": "#ec4899",
};

const MOCK_COMPONENTS: RecognizedComponent[] = [
  { id: "C-1",   type: "框架柱", count: 24, spec: "600×600",  confidence: 98.2, color: "#3b82f6", bbox: { x: 140, y: 120, w: 30, h: 30 } },
  { id: "C-2",   type: "框架柱", count: 18, spec: "500×500",  confidence: 97.5, color: "#3b82f6", bbox: { x: 300, y: 120, w: 26, h: 26 } },
  { id: "B-KL1", type: "框架梁", count: 36, spec: "300×600",  confidence: 99.1, color: "#10b981", bbox: { x: 155, y: 132, w: 300, h: 10 } },
  { id: "B-KL2", type: "框架梁", count: 28, spec: "250×500",  confidence: 98.4, color: "#10b981", bbox: { x: 155, y: 350, w: 300, h: 10 } },
  { id: "W-1",   type: "剪力墙", count: 12, spec: "T=250",    confidence: 94.5, color: "#f59e0b", bbox: { x: 126, y: 135, w: 10, h: 220 } },
  { id: "W-2",   type: "剪力墙", count: 8,  spec: "T=200",    confidence: 93.8, color: "#f59e0b", bbox: { x: 854, y: 135, w: 10, h: 220 } },
  { id: "B-LL2", type: "连梁",   count: 42, spec: "250×400",  confidence: 96.8, color: "#06b6d4", bbox: { x: 126, y: 350, w: 30, h: 8 } },
  { id: "S-L1",  type: "楼板",   count: 8,  spec: "H=120",    confidence: 95.2, color: "#8b5cf6" },
  { id: "S-L2",  type: "楼板",   count: 6,  spec: "H=100",    confidence: 94.0, color: "#8b5cf6" },
  { id: "FD-1",  type: "基础",   count: 4,  spec: "1200×1200", confidence: 92.3, color: "#ec4899" },
];

const LEGEND = [
  { label: "框架柱 Columns", color: "#3b82f6" },
  { label: "框架梁 Beams",   color: "#10b981" },
  { label: "剪力墙 Walls",   color: "#f59e0b" },
  { label: "连梁 Coupling",  color: "#06b6d4" },
  { label: "楼板 Slabs",     color: "#8b5cf6" },
  { label: "基础 Footings",  color: "#ec4899" },
];

/* ─── Axis grid data ────────────────────── */
const AXIS_X = [
  { label: "①", v: 140 }, { label: "②", v: 300 }, { label: "③", v: 460 },
  { label: "④", v: 620 }, { label: "⑤", v: 780 }, { label: "⑥", v: 860 },
];
const AXIS_Y = [
  { label: "Ⓐ", v: 120 }, { label: "Ⓑ", v: 280 }, { label: "Ⓒ", v: 360 },
  { label: "Ⓓ", v: 500 }, { label: "Ⓔ", v: 620 },
];

/* Column positions in the structural grid */
const COL_POSITIONS = [
  [140,120],[300,120],[460,120],[620,120],[780,120],
  [140,280],[300,280],[460,280],[620,280],[780,280],
  [140,360],[300,360],[460,360],[620,360],[780,360],
  [140,500],[300,500],[460,500],[620,500],[780,500],
  [140,620],[300,620],[460,620],[620,620],[780,620],
];

export default function DrawingRecognition() {
  const { projectId: _pid } = useParams<{ projectId: string }>();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"2D" | "3D">("2D");
  const [activeTool, setActiveTool] = useState<string>("select");
  const [showLabels, setShowLabels] = useState(true);
  const [cadImage, setCadImage] = useState<string | null>(null);
  const [cadOpacity, setCadOpacity] = useState(0.6);
  const [recognizing, setRecognizing] = useState(false);
  const [components, setComponents] = useState<RecognizedComponent[]>(MOCK_COMPONENTS);
  const [boqSuggestions, setBoqSuggestions] = useState<BoqSuggestion[]>([]);
  const [aiSummary, setAiSummary] = useState<string>("");
  const [usingMock, setUsingMock] = useState(true);

  /* ── Zoom & Pan state ── */
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const isPanning = useRef(false);
  const lastMouse = useRef({ x: 0, y: 0 });
  const canvasRef = useRef<HTMLDivElement>(null);

  const totalComponents = components.reduce((s, c) => s + c.count, 0);
  const avgConfidence = components.length
    ? (components.reduce((s, c) => s + c.confidence, 0) / components.length).toFixed(1)
    : "0.0";

  const handleZoom = useCallback((delta: number) => {
    setZoom((z) => Math.max(0.3, Math.min(5, z + delta)));
  }, []);

  const resetView = useCallback(() => { setZoom(1); setPan({ x: 0, y: 0 }); }, []);

  /* Mouse wheel zoom */
  useEffect(() => {
    const el = canvasRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      handleZoom(e.deltaY > 0 ? -0.1 : 0.1);
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [handleZoom]);

  /* Mouse drag pan */
  const onMouseDown = (e: React.MouseEvent) => {
    if (activeTool !== "select" && activeTool !== "pan") return;
    isPanning.current = true;
    lastMouse.current = { x: e.clientX, y: e.clientY };
  };
  const onMouseMove = (e: React.MouseEvent) => {
    if (!isPanning.current) return;
    const dx = e.clientX - lastMouse.current.x;
    const dy = e.clientY - lastMouse.current.y;
    lastMouse.current = { x: e.clientX, y: e.clientY };
    setPan((p) => ({ x: p.x + dx, y: p.y + dy }));
  };
  const onMouseUp = () => { isPanning.current = false; };

  /* CAD file upload + AI recognition */
  const handleCadUpload = async (file: File) => {
    const url = URL.createObjectURL(file);
    setCadImage(url);
    message.success(`已加载图纸: ${file.name}`);

    // Attempt AI recognition
    setRecognizing(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API_BASE}/drawing-recognition`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) throw new Error(`${res.status}`);
      const data = await res.json();

      if (data.error) {
        message.warning(`AI识别失败: ${data.error}，使用示例数据`);
      } else if (data.components?.length > 0) {
        const mapped: RecognizedComponent[] = data.components.map((c: any) => ({
          id: c.id,
          type: c.type,
          count: c.count,
          spec: c.spec,
          confidence: c.confidence,
          color: TYPE_COLOR_MAP[c.type] || "#94a3b8",
        }));
        setComponents(mapped);
        setBoqSuggestions(data.boq_suggestions || []);
        setAiSummary(data.summary || "");
        setUsingMock(false);
        message.success(`AI识别完成: ${data.components.length} 类构件`);
      } else {
        message.info("AI未识别到构件，保留示例数据");
      }
    } catch {
      message.warning("AI识别服务不可用，使用示例数据");
    } finally {
      setRecognizing(false);
    }
    return false;
  };

  return (
    <div className="dr-root">
      <PageBreadcrumb items={[
        { label: "控制台", path: "/dashboard" },
        { label: "项目管理", path: "/projects" },
        { label: "图纸 AI 识别详情" },
      ]} />

      {/* Header */}
      <header className="dr-header">
        <div>
          <h1 className="dr-title">图纸 AI 识别详情</h1>
          <p className="dr-subtitle">当前项目：世茂广场 A 座施工图 - 地下二层结构平面图</p>
        </div>
        <div className="dr-header-actions">
          <button className="dr-btn-outline" onClick={() => message.info("导出功能开发中...")}>
            <span className="material-symbols-outlined">download</span>
            导出清单
          </button>
          <button className="dr-btn-primary" onClick={() => message.success("识别结果已保存")}>
            <span className="material-symbols-outlined">save</span>
            保存识别结果
          </button>
        </div>
      </header>

      {/* Main Grid */}
      <div className="dr-grid">
        {/* Left: Drawing Viewer */}
        <div className="dr-viewer">
          {/* Toolbar */}
          <div className="dr-toolbar">
            <div className="dr-toolbar-left">
              <button className="dr-tool-btn" title="放大" onClick={() => handleZoom(0.2)}>
                <span className="material-symbols-outlined">zoom_in</span>
              </button>
              <button className="dr-tool-btn" title="缩小" onClick={() => handleZoom(-0.2)}>
                <span className="material-symbols-outlined">zoom_out</span>
              </button>
              <button className="dr-tool-btn" title="重置视图" onClick={resetView}>
                <span className="material-symbols-outlined">fit_screen</span>
              </button>
              <div className="dr-toolbar-divider" />
              <button
                className={`dr-tool-btn label ${activeTool === "select" ? "active" : ""}`}
                onClick={() => setActiveTool("select")}
              >
                <span className="material-symbols-outlined">select_window</span>
                区域选择
              </button>
              <button
                className={`dr-tool-btn label ${activeTool === "measure" ? "active" : ""}`}
                onClick={() => setActiveTool("measure")}
              >
                <span className="material-symbols-outlined">straighten</span>
                手动测量
              </button>
              <div className="dr-toolbar-divider" />
              <Upload accept="image/*,.dxf,.dwg,.pdf" showUploadList={false} beforeUpload={handleCadUpload}>
                <button className="dr-tool-btn label">
                  <span className="material-symbols-outlined">upload_file</span>
                  加载图纸
                </button>
              </Upload>
              <button
                className={`dr-tool-btn label ${showLabels ? "active" : ""}`}
                onClick={() => setShowLabels((v) => !v)}
              >
                <span className="material-symbols-outlined">label</span>
                标注
              </button>
            </div>
            <div className="dr-toolbar-right">
              <span className="dr-toolbar-hint">{Math.round(zoom * 100)}%</span>
              <div className="dr-view-toggle">
                <button className={viewMode === "2D" ? "active" : ""} onClick={() => setViewMode("2D")}>2D</button>
                <button className={viewMode === "3D" ? "active" : ""} onClick={() => setViewMode("3D")}>3D</button>
              </div>
            </div>
          </div>

          {/* Canvas with zoom/pan */}
          <div
            className="dr-canvas"
            ref={canvasRef}
            onMouseDown={onMouseDown}
            onMouseMove={onMouseMove}
            onMouseUp={onMouseUp}
            onMouseLeave={onMouseUp}
          >
            <div className="dr-canvas-grid" />
            <div
              className="dr-canvas-transform"
              style={{
                transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
              }}
            >
              {/* CAD background image (if uploaded) */}
              {cadImage && (
                <img
                  src={cadImage}
                  alt="CAD Drawing"
                  className="dr-cad-image"
                  style={{ opacity: cadOpacity }}
                  draggable={false}
                />
              )}

              {/* SVG structural drawing */}
              <svg className="dr-blueprint-svg" viewBox="0 0 1000 750" xmlns="http://www.w3.org/2000/svg">
                <defs>
                  {/* Hatch pattern for slabs */}
                  <pattern id="hatch-slab" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                    <line x1="0" y1="0" x2="0" y2="8" stroke="rgba(139,92,246,0.15)" strokeWidth="1" />
                  </pattern>
                  {/* Hatch pattern for walls */}
                  <pattern id="hatch-wall" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                    <line x1="0" y1="0" x2="0" y2="6" stroke="rgba(245,158,11,0.25)" strokeWidth="1" />
                  </pattern>
                  {/* Column fill */}
                  <pattern id="hatch-col" width="4" height="4" patternUnits="userSpaceOnUse">
                    <line x1="0" y1="0" x2="4" y2="4" stroke="rgba(59,130,246,0.3)" strokeWidth="0.5" />
                    <line x1="4" y1="0" x2="0" y2="4" stroke="rgba(59,130,246,0.3)" strokeWidth="0.5" />
                  </pattern>
                </defs>

                {/* ── Background ── */}
                <rect width="1000" height="750" fill="rgba(8,12,21,0.95)" />

                {/* ── Axis grid lines ── */}
                {AXIS_X.map((a) => (
                  <g key={`ax-${a.label}`}>
                    <line x1={a.v} y1="70" x2={a.v} y2="680" stroke="rgba(59,130,246,0.08)" strokeWidth="0.5" strokeDasharray="4 4" />
                    <circle cx={a.v} cy="55" r="14" fill="none" stroke="rgba(148,163,184,0.35)" strokeWidth="1" />
                    <text x={a.v} y="60" fill="rgba(148,163,184,0.6)" fontSize="13" textAnchor="middle" fontFamily="serif">{a.label}</text>
                    <circle cx={a.v} cy="695" r="14" fill="none" stroke="rgba(148,163,184,0.35)" strokeWidth="1" />
                    <text x={a.v} y="700" fill="rgba(148,163,184,0.6)" fontSize="13" textAnchor="middle" fontFamily="serif">{a.label}</text>
                  </g>
                ))}
                {AXIS_Y.map((a) => (
                  <g key={`ay-${a.label}`}>
                    <line x1="90" y1={a.v} x2="910" y2={a.v} stroke="rgba(59,130,246,0.08)" strokeWidth="0.5" strokeDasharray="4 4" />
                    <circle cx="55" cy={a.v} r="14" fill="none" stroke="rgba(148,163,184,0.35)" strokeWidth="1" />
                    <text x="55" y={a.v + 5} fill="rgba(148,163,184,0.6)" fontSize="13" textAnchor="middle" fontFamily="serif">{a.label}</text>
                    <circle cx="945" cy={a.v} r="14" fill="none" stroke="rgba(148,163,184,0.35)" strokeWidth="1" />
                    <text x="945" y={a.v + 5} fill="rgba(148,163,184,0.6)" fontSize="13" textAnchor="middle" fontFamily="serif">{a.label}</text>
                  </g>
                ))}

                {/* ── Slab hatching (floor plates) ── */}
                <rect x="140" y="120" width="640" height="160" fill="url(#hatch-slab)" />
                <rect x="140" y="360" width="640" height="140" fill="url(#hatch-slab)" />
                <rect x="140" y="500" width="480" height="120" fill="url(#hatch-slab)" />

                {/* ── Beams (horizontal) ── */}
                {[120, 280, 360, 500, 620].map((y) => (
                  <line key={`bh-${y}`} x1="140" y1={y} x2="780" y2={y} stroke="#10b981" strokeWidth="4" opacity="0.5" />
                ))}
                {/* Beams (vertical) */}
                {[140, 300, 460, 620, 780].map((x) => (
                  <line key={`bv-${x}`} x1={x} y1="120" x2={x} y2="620" stroke="#10b981" strokeWidth="4" opacity="0.5" />
                ))}
                {/* Extra span beam */}
                <line x1="780" y1="120" x2="860" y2="120" stroke="#10b981" strokeWidth="3" opacity="0.4" />
                <line x1="780" y1="280" x2="860" y2="280" stroke="#10b981" strokeWidth="3" opacity="0.4" />
                <line x1="860" y1="120" x2="860" y2="280" stroke="#10b981" strokeWidth="3" opacity="0.4" />

                {/* ── Shear walls ── */}
                {/* Left edge walls */}
                <rect x="126" y="120" width="12" height="160" fill="url(#hatch-wall)" stroke="#f59e0b" strokeWidth="1.5" />
                <rect x="126" y="360" width="12" height="140" fill="url(#hatch-wall)" stroke="#f59e0b" strokeWidth="1.5" />
                <rect x="126" y="500" width="12" height="120" fill="url(#hatch-wall)" stroke="#f59e0b" strokeWidth="1.5" />
                {/* Right edge walls */}
                <rect x="854" y="120" width="12" height="160" fill="url(#hatch-wall)" stroke="#f59e0b" strokeWidth="1.5" />
                {/* Core walls */}
                <rect x="440" y="280" width="12" height="80" fill="url(#hatch-wall)" stroke="#f59e0b" strokeWidth="1.5" />
                <rect x="480" y="280" width="12" height="80" fill="url(#hatch-wall)" stroke="#f59e0b" strokeWidth="1.5" />
                <rect x="440" y="280" width="52" height="12" fill="url(#hatch-wall)" stroke="#f59e0b" strokeWidth="1.5" />

                {/* ── Coupling beams (cyan) ── */}
                <rect x="126" y="276" width="30" height="8" fill="#06b6d4" opacity="0.5" rx="1" />
                <rect x="126" y="496" width="30" height="8" fill="#06b6d4" opacity="0.5" rx="1" />
                <rect x="452" y="350" width="28" height="8" fill="#06b6d4" opacity="0.5" rx="1" />

                {/* ── Columns ── */}
                {COL_POSITIONS.map(([x, y], i) => (
                  <g key={`col-${i}`}>
                    <rect x={x - 13} y={y - 13} width="26" height="26" fill="url(#hatch-col)" stroke="#3b82f6" strokeWidth="1.5" />
                    {/* Diagonal cross for RC column convention */}
                    <line x1={x - 11} y1={y - 11} x2={x + 11} y2={y + 11} stroke="rgba(59,130,246,0.4)" strokeWidth="0.7" />
                    <line x1={x + 11} y1={y - 11} x2={x - 11} y2={y + 11} stroke="rgba(59,130,246,0.4)" strokeWidth="0.7" />
                  </g>
                ))}
                {/* Cantilever column */}
                <rect x="847" y="107" width="26" height="26" fill="url(#hatch-col)" stroke="#3b82f6" strokeWidth="1.5" />
                <line x1="849" y1="109" x2="871" y2="131" stroke="rgba(59,130,246,0.4)" strokeWidth="0.7" />
                <line x1="871" y1="109" x2="849" y2="131" stroke="rgba(59,130,246,0.4)" strokeWidth="0.7" />
                <rect x="847" y="267" width="26" height="26" fill="url(#hatch-col)" stroke="#3b82f6" strokeWidth="1.5" />

                {/* ── Footing outlines (dashed pink) ── */}
                <rect x="110" y="90" width="60" height="60" fill="none" stroke="#ec4899" strokeWidth="1" strokeDasharray="5 3" opacity="0.5" />
                <rect x="750" y="90" width="60" height="60" fill="none" stroke="#ec4899" strokeWidth="1" strokeDasharray="5 3" opacity="0.5" />
                <rect x="110" y="590" width="60" height="60" fill="none" stroke="#ec4899" strokeWidth="1" strokeDasharray="5 3" opacity="0.5" />
                <rect x="750" y="590" width="60" height="60" fill="none" stroke="#ec4899" strokeWidth="1" strokeDasharray="5 3" opacity="0.5" />

                {/* ── Dimension lines ── */}
                {/* Top dimension: axis ①→② */}
                <g className="dr-dim">
                  <line x1="140" y1="38" x2="300" y2="38" stroke="rgba(248,113,113,0.6)" strokeWidth="0.7" />
                  <line x1="140" y1="34" x2="140" y2="42" stroke="rgba(248,113,113,0.6)" strokeWidth="0.7" />
                  <line x1="300" y1="34" x2="300" y2="42" stroke="rgba(248,113,113,0.6)" strokeWidth="0.7" />
                  <text x="220" y="35" fill="rgba(248,113,113,0.7)" fontSize="9" textAnchor="middle">8100</text>
                </g>
                {/* axis ②→③ */}
                <g className="dr-dim">
                  <line x1="300" y1="38" x2="460" y2="38" stroke="rgba(248,113,113,0.6)" strokeWidth="0.7" />
                  <line x1="460" y1="34" x2="460" y2="42" stroke="rgba(248,113,113,0.6)" strokeWidth="0.7" />
                  <text x="380" y="35" fill="rgba(248,113,113,0.7)" fontSize="9" textAnchor="middle">8100</text>
                </g>
                {/* Right dimension: axis Ⓐ→Ⓑ */}
                <g className="dr-dim">
                  <line x1="920" y1="120" x2="920" y2="280" stroke="rgba(248,113,113,0.6)" strokeWidth="0.7" />
                  <line x1="916" y1="120" x2="924" y2="120" stroke="rgba(248,113,113,0.6)" strokeWidth="0.7" />
                  <line x1="916" y1="280" x2="924" y2="280" stroke="rgba(248,113,113,0.6)" strokeWidth="0.7" />
                  <text x="930" y="204" fill="rgba(248,113,113,0.7)" fontSize="9" textAnchor="start" transform="rotate(-90 930 204)">6600</text>
                </g>

                {/* ── Section cut markers ── */}
                <g>
                  <line x1="90" y1="200" x2="110" y2="200" stroke="rgba(248,113,113,0.6)" strokeWidth="1.5" />
                  <circle cx="102" cy="200" r="8" fill="none" stroke="rgba(248,113,113,0.6)" strokeWidth="1" />
                  <text x="102" y="203" fill="rgba(248,113,113,0.6)" fontSize="7" textAnchor="middle">1</text>
                  <line x1="890" y1="200" x2="910" y2="200" stroke="rgba(248,113,113,0.6)" strokeWidth="1.5" />
                  <polygon points="908,196 916,200 908,204" fill="rgba(248,113,113,0.6)" />
                </g>

                {/* ── Column labels (when showLabels) ── */}
                {showLabels && (
                  <g>
                    <text x="140" y="100" fill="rgba(59,130,246,0.7)" fontSize="8" textAnchor="middle" fontWeight="600">C1</text>
                    <text x="300" y="100" fill="rgba(59,130,246,0.7)" fontSize="8" textAnchor="middle" fontWeight="600">C2</text>
                    <text x="460" y="100" fill="rgba(59,130,246,0.7)" fontSize="8" textAnchor="middle" fontWeight="600">C3</text>
                    <text x="620" y="100" fill="rgba(59,130,246,0.7)" fontSize="8" textAnchor="middle" fontWeight="600">C4</text>
                    <text x="780" y="100" fill="rgba(59,130,246,0.7)" fontSize="8" textAnchor="middle" fontWeight="600">C5</text>
                  </g>
                )}

                {/* ── Beam labels ── */}
                {showLabels && (
                  <g>
                    <text x="220" y="115" fill="rgba(16,185,129,0.7)" fontSize="7" textAnchor="middle">KL1 300×600</text>
                    <text x="540" y="115" fill="rgba(16,185,129,0.7)" fontSize="7" textAnchor="middle">KL1 300×600</text>
                    <text x="220" y="355" fill="rgba(16,185,129,0.7)" fontSize="7" textAnchor="middle">KL2 250×500</text>
                    <text x="540" y="355" fill="rgba(16,185,129,0.7)" fontSize="7" textAnchor="middle">KL2 250×500</text>
                  </g>
                )}

                {/* ── Wall labels ── */}
                {showLabels && (
                  <g>
                    <text x="115" y="200" fill="rgba(245,158,11,0.7)" fontSize="7" textAnchor="end" transform="rotate(-90 115 200)">Q1 T=250</text>
                    <text x="880" y="200" fill="rgba(245,158,11,0.7)" fontSize="7" textAnchor="end" transform="rotate(-90 880 200)">Q2 T=200</text>
                  </g>
                )}

                {/* ── Title block (bottom-right) ── */}
                <rect x="720" y="700" width="270" height="40" fill="rgba(15,23,42,0.9)" stroke="rgba(148,163,184,0.2)" strokeWidth="1" />
                <text x="730" y="717" fill="rgba(148,163,184,0.5)" fontSize="8">世茂广场 A 座 / 地下二层结构平面图</text>
                <text x="730" y="732" fill="rgba(148,163,184,0.35)" fontSize="7">比例 1:100 | 日期 2024-03-05 | Rev.A</text>

                {/* ── Highlight selected component bbox ── */}
                {components.filter((c) => c.id === selectedId && c.bbox).map((c) => (
                  <rect
                    key={`sel-${c.id}`}
                    x={c.bbox!.x - 4}
                    y={c.bbox!.y - 4}
                    width={c.bbox!.w + 8}
                    height={c.bbox!.h + 8}
                    fill="none"
                    stroke="#fff"
                    strokeWidth="2"
                    strokeDasharray="6 3"
                    opacity="0.8"
                  >
                    <animate attributeName="stroke-dashoffset" from="0" to="18" dur="1s" repeatCount="indefinite" />
                  </rect>
                ))}
              </svg>
            </div>

            {/* Legend overlay */}
            <div className="dr-legend">
              {LEGEND.map((l) => (
                <div key={l.label} className="dr-legend-item">
                  <span className="dr-legend-dot" style={{ background: l.color }} />
                  <span>{l.label}</span>
                </div>
              ))}
            </div>

            {/* Zoom indicator */}
            <div className="dr-zoom-indicator">{Math.round(zoom * 100)}%</div>

            {/* CAD opacity slider (if image loaded) */}
            {cadImage && (
              <div className="dr-cad-controls">
                <span className="dr-cad-controls-label">图纸透明度</span>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={cadOpacity * 100}
                  onChange={(e) => setCadOpacity(Number(e.target.value) / 100)}
                  className="dr-cad-slider"
                />
                <button className="dr-tool-btn" onClick={() => { setCadImage(null); message.info("已移除底图"); }}>
                  <span className="material-symbols-outlined">close</span>
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Right Panel */}
        <div className="dr-panel">
          {/* AI Status Card */}
          <div className="dr-ai-card">
            <div className="dr-ai-card-head">
              <h3>
                <span className="material-symbols-outlined">analytics</span>
                AI 识别概览
              </h3>
              <span className="dr-confidence-badge">{usingMock ? "示例数据" : "AI识别"}</span>
            </div>
            <div className="dr-ai-stats">
              <div className="dr-ai-stat">
                <p className="dr-ai-stat-label">平均置信度</p>
                <p className="dr-ai-stat-value primary">{avgConfidence}%</p>
              </div>
              <div className="dr-ai-stat">
                <p className="dr-ai-stat-label">识别构件数</p>
                <p className="dr-ai-stat-value">{totalComponents} 个</p>
              </div>
            </div>
            <div className="dr-ai-stats" style={{ marginTop: 8 }}>
              <div className="dr-ai-stat">
                <p className="dr-ai-stat-label">构件大类</p>
                <p className="dr-ai-stat-value">{LEGEND.length}</p>
              </div>
              <div className="dr-ai-stat">
                <p className="dr-ai-stat-label">图纸底图</p>
                <p className="dr-ai-stat-value" style={{ fontSize: 14 }}>{cadImage ? "已加载" : "未加载"}</p>
              </div>
            </div>
          </div>

          {/* Manual Tools */}
          <div className="dr-tools-card">
            <h3>
              <span className="material-symbols-outlined">tune</span>
              手动调整工具
            </h3>
            <div className="dr-tools-grid">
              <button className="dr-tools-btn" onClick={() => message.info("修正属性功能开发中...")}>
                <span className="material-symbols-outlined">edit_square</span> 修正属性
              </button>
              <button className="dr-tools-btn" onClick={() => message.info("新增构件功能开发中...")}>
                <span className="material-symbols-outlined">add_box</span> 新增构件
              </button>
              <button className="dr-tools-btn" onClick={() => message.info("删除错误功能开发中...")}>
                <span className="material-symbols-outlined">delete</span> 删除错误
              </button>
              <button className="dr-tools-btn" onClick={() => message.info("合并构件功能开发中...")}>
                <span className="material-symbols-outlined">merge</span> 合并构件
              </button>
            </div>
          </div>

          {/* Components List */}
          <div className="dr-list-card">
            <div className="dr-list-head">
              <h3>识别清单</h3>
              <div className="dr-list-actions">
                <span className="material-symbols-outlined">filter_list</span>
                <span className="material-symbols-outlined">search</span>
              </div>
            </div>
            <div className="dr-list-body">
              <table className="dr-table">
                <thead>
                  <tr>
                    <th>编号</th>
                    <th>构件类型</th>
                    <th style={{ textAlign: "center" }}>数量</th>
                    <th>主规格</th>
                    <th style={{ textAlign: "right" }}>置信度</th>
                  </tr>
                </thead>
                <tbody>
                  {recognizing ? (
                    <tr><td colSpan={5} style={{ textAlign: "center", padding: 24 }}><Spin /> AI识别中...</td></tr>
                  ) : components.map((c) => (
                    <tr
                      key={c.id}
                      className={selectedId === c.id ? "selected" : ""}
                      onClick={() => setSelectedId(selectedId === c.id ? null : c.id)}
                    >
                      <td className="dr-cell-id" style={{ color: c.color }}>{c.id}</td>
                      <td className="dr-cell-type">
                        <span className="dr-cell-dot" style={{ background: c.color }} />
                        {c.type}
                      </td>
                      <td style={{ textAlign: "center" }}>{c.count}</td>
                      <td className="dr-cell-spec">{c.spec}</td>
                      <td style={{ textAlign: "right" }}>
                        <span className={`dr-conf-tag ${c.confidence >= 97 ? "high" : c.confidence >= 94 ? "mid" : "low"}`}>
                          {c.confidence}%
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="dr-list-footer">
              <span>显示 {components.length} 个构件大类 / {totalComponents} 个构件</span>
              <button className="dr-list-more">查看详情</button>
            </div>

            {/* BOQ Suggestions from AI recognition */}
            {boqSuggestions.length > 0 && (
              <div style={{ padding: "8px 12px", borderTop: "1px solid rgba(148,163,184,0.1)" }}>
                <h4 style={{ color: "rgba(148,163,184,0.7)", fontSize: 12, marginBottom: 6 }}>AI 建议清单项</h4>
                {boqSuggestions.map((s) => (
                  <div key={s.source_component_id} style={{ fontSize: 11, color: "rgba(148,163,184,0.6)", marginBottom: 4 }}>
                    <span style={{ color: "#3b82f6" }}>{s.suggested_code}</span>{" "}
                    {s.suggested_name} ({s.suggested_unit})
                    {s.suggested_quantity > 0 && <span> ≈{s.suggested_quantity}</span>}
                  </div>
                ))}
              </div>
            )}

            {aiSummary && (
              <div style={{ padding: "8px 12px", borderTop: "1px solid rgba(148,163,184,0.1)", fontSize: 11, color: "rgba(148,163,184,0.5)" }}>
                {aiSummary}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
