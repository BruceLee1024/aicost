export default function ContactUs() {
  return (
    <div className="contact-page">
      {/* Hero */}
      <section className="contact-hero">
        <div className="contact-hero-glow" />
        <div className="contact-hero-inner">
          <span className="contact-badge">
            <span className="material-symbols-outlined" style={{ fontSize: 14 }}>auto_awesome</span>
            关于作者
          </span>
          <h1>
            用 AI 重塑<span className="contact-accent">工程造价</span>的未来
          </h1>
          <p className="contact-hero-desc">
            我始终相信，人工智能不应只停留在实验室，而应真正走进工程造价的每一个环节。
            从清单编制到定额匹配，从市场价分析到合规审计——AI 有潜力让这一切变得更精准、更高效、更智能。
          </p>
        </div>
      </section>

      {/* Vision Cards */}
      <section className="contact-vision">
        <div className="contact-vision-grid">
          {[
            {
              icon: "neurology",
              title: "探索 · AI + 造价",
              desc: "工程造价行业积累了海量的数据与经验，但数字化转型仍处于早期。我正在探索如何将大语言模型、多模态识别等前沿 AI 技术，与造价专业知识深度融合，打造真正懂行业的智能工具。",
              gradient: "linear-gradient(135deg, #1456b8 0%, #22a2f2 100%)",
            },
            {
              icon: "handshake",
              title: "开放 · 共同成长",
              desc: "独行快，众行远。无论你是造价工程师、软件开发者，还是对 AI + 建筑行业感兴趣的同道中人，我都非常期待与你交流。让我们一起碰撞想法、共享资源、共同推动行业变革。",
              gradient: "linear-gradient(135deg, #8b5cf6 0%, #a78bfa 100%)",
            },
            {
              icon: "rocket_launch",
              title: "愿景 · 降本增效",
              desc: "我的目标很简单：让每一位造价从业者都能借助 AI 的力量，从重复性劳动中解放出来，将更多精力投入到专业判断和价值创造中。技术不是替代人，而是赋能人。",
              gradient: "linear-gradient(135deg, #22c55e 0%, #4ade80 100%)",
            },
          ].map((item) => (
            <div key={item.title} className="contact-vision-card">
              <div className="contact-vision-icon" style={{ background: item.gradient }}>
                <span className="material-symbols-outlined">{item.icon}</span>
              </div>
              <h3>{item.title}</h3>
              <p>{item.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Contact Card */}
      <section className="contact-card-section">
        <div className="contact-card">
          <div className="contact-card-left">
            <h2>如果你也对此感兴趣</h2>
            <p>
              欢迎扫码添加我的微信，无论是技术探讨、产品建议，还是合作意向，我都乐于交流。
              期待与志同道合的你相识。
            </p>
            <div className="contact-wechat-id">
              <span className="material-symbols-outlined">chat</span>
              <span>微信号：<strong>Changning_Lee</strong></span>
            </div>
          </div>
          <div className="contact-card-right">
            <div className="contact-qr-wrapper">
              <img src={`${import.meta.env.BASE_URL}qrcode.jpg`} alt="微信二维码" />
            </div>
            <span className="contact-qr-hint">微信扫一扫，添加好友</span>
          </div>
        </div>
      </section>
    </div>
  );
}
