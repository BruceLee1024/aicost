import { useNavigate } from "react-router-dom";

export interface BreadcrumbItem {
  label: string;
  path?: string;
}

interface Props {
  items: BreadcrumbItem[];
}

export default function PageBreadcrumb({ items }: Props) {
  const navigate = useNavigate();

  return (
    <nav className="page-breadcrumb">
      {items.map((item, i) => {
        const isLast = i === items.length - 1;
        return (
          <span key={i} className="page-breadcrumb-segment">
            {item.path && !isLast ? (
              <button className="page-breadcrumb-link" onClick={() => navigate(item.path!)}>
                {item.label}
              </button>
            ) : (
              <span className={isLast ? "page-breadcrumb-current" : "page-breadcrumb-text"}>
                {item.label}
              </span>
            )}
            {!isLast && (
              <span className="material-symbols-outlined page-breadcrumb-sep">chevron_right</span>
            )}
          </span>
        );
      })}
    </nav>
  );
}
