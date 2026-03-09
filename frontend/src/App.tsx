import { useState } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { App as AntApp, ConfigProvider, Modal, theme } from "antd";
import zhCN from "antd/locale/zh_CN";
import LandingPage from "./pages/LandingPage";
import Dashboard from "./pages/Dashboard";
import ProjectList from "./pages/ProjectList";
import ProjectDetail from "./pages/ProjectDetail";
import PricingManagement from "./pages/PricingManagement";
import SystemSettings from "./pages/SystemSettings";
import ReportsPage from "./pages/ReportsPage";
import RuleConfig from "./pages/RuleConfig";
import UnitPriceAnalysis from "./pages/UnitPriceAnalysis";
import DrawingRecognition from "./pages/DrawingRecognition";
import AuditWorkbench from "./pages/AuditWorkbench";
import ContactUs from "./pages/ContactUs";

const NAV_ITEMS = [
  { path: "/dashboard", icon: "dashboard", label: "仪表盘" },
  { path: "/projects", icon: "analytics", label: "项目管理" },
  { path: "/drawings", icon: "draw", label: "图纸库" },
  { path: "/pricing", icon: "calculate", label: "计价管理" },
  { path: "/reports", icon: "description", label: "报表中心" },
  { path: "/rules", icon: "rule", label: "规则配置" },
  { path: "/audits", icon: "contract", label: "审计管理" },
  { path: "/contact", icon: "connect_without_contact", label: "联系我们" },
  { path: "/settings", icon: "settings", label: "系统设置" },
];

function AppSidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const [contactOpen, setContactOpen] = useState(false);

  return (
    <aside className="app-sidebar">
      <div className="app-sidebar-top">
        {/* Brand */}
        <a
          href="/projects"
          className="app-sidebar-brand"
          onClick={(e) => { e.preventDefault(); navigate("/projects"); }}
        >
          <div className="app-sidebar-brand-icon">
            <span className="material-symbols-outlined">architecture</span>
          </div>
          <div className="app-sidebar-brand-text">
            <h1>智价 AI</h1>
            <p>Cost Management System</p>
          </div>
        </a>
        {/* Nav */}
        <nav className="app-sidebar-nav">
          {NAV_ITEMS.map((item) => {
            const active = location.pathname.startsWith(item.path);
            return (
              <a
                key={item.path}
                href={item.path}
                className={`app-sidebar-link${active ? " active" : ""}`}
                onClick={(e) => { e.preventDefault(); navigate(item.path); }}
              >
                <span className="material-symbols-outlined">{item.icon}</span>
                <span>{item.label}</span>
              </a>
            );
          })}
        </nav>
      </div>
      {/* Contact author */}
      <div className="app-sidebar-contact">
        <button className="app-sidebar-contact-btn" onClick={() => setContactOpen(true)}>
          <span className="material-symbols-outlined">qr_code_2</span>
          <span>添加微信</span>
        </button>
      </div>
      {/* User profile */}
      <div className="app-sidebar-footer">
        <div className="app-sidebar-user">
          <div className="app-sidebar-avatar">B</div>
          <div className="app-sidebar-user-info">
            <p className="app-sidebar-user-name">Bruce</p>
            <p className="app-sidebar-user-role">项目经理</p>
          </div>
          <span className="material-symbols-outlined app-sidebar-more">more_vert</span>
        </div>
      </div>
      <Modal
        open={contactOpen}
        onCancel={() => setContactOpen(false)}
        footer={null}
        centered
        width={360}
        title={null}
        className="contact-modal"
      >
        <div className="contact-modal-body">
          <img src="/qrcode.jpg" alt="联系作者" className="contact-qrcode" />
          <h3>添加微信</h3>
          <p>微信号：Changning_Lee</p>
          <p style={{ marginTop: 4 }}>扫描二维码，与我取得联系</p>
        </div>
      </Modal>
    </aside>
  );
}

export default function App() {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorPrimary: "#1456b8",
          borderRadius: 8,
          fontFamily: '"Inter", "Manrope", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
          colorBgContainer: "#151b28",
          colorBgElevated: "#1c2537",
          colorBorder: "#1e293b",
          colorText: "#e2e8f0",
          colorTextSecondary: "#94a3b8",
        },
      }}
    >
      <AntApp>
        <BrowserRouter basename={import.meta.env.BASE_URL.replace(/\/$/, '')}>
          <Routes>
            {/* Landing page — no sidebar */}
            <Route path="/" element={<LandingPage />} />

            {/* App shell — sidebar + main */}
            <Route path="/*" element={
              <div className="app-layout">
                <AppSidebar />
                <main className="app-main">
                  <Routes>
                    <Route path="/dashboard" element={<Dashboard />} />
                    <Route path="/projects" element={<ProjectList />} />
                    <Route path="/projects/:id" element={<ProjectDetail />} />
                    <Route path="/pricing" element={<PricingManagement />} />
                    <Route path="/pricing/analysis/:projectId/:boqItemId" element={<UnitPriceAnalysis />} />
                    <Route path="/drawings" element={<DrawingRecognition />} />
                    <Route path="/drawings/:projectId" element={<DrawingRecognition />} />
                    <Route path="/reports" element={<ReportsPage />} />
                    <Route path="/rules" element={<RuleConfig />} />
                    <Route path="/audits" element={<AuditWorkbench />} />
                    <Route path="/contact" element={<ContactUs />} />
                    <Route path="/settings" element={<div className="page-container"><SystemSettings /></div>} />
                    <Route path="*" element={<Navigate to="/dashboard" replace />} />
                  </Routes>
                </main>
              </div>
            } />
          </Routes>
        </BrowserRouter>
      </AntApp>
    </ConfigProvider>
  );
}
