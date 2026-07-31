"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/", label: "Dashboard", icon: "◉" },
  { href: "/agent", label: "Agent", icon: "◎" },
  { href: "/analytics", label: "Analytics", icon: "▤" },
  { href: "/settings", label: "Settings", icon: "⚙" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside
      style={{
        position: "fixed",
        left: 0,
        top: 0,
        width: "var(--sidebar-width)",
        height: "100vh",
        background: "var(--bg-secondary)",
        borderRight: "1px solid var(--border)",
        display: "flex",
        flexDirection: "column",
        zIndex: 100,
      }}
    >
      <div
        style={{
          padding: "1.5rem",
          borderBottom: "1px solid var(--border)",
        }}
      >
        <h2 style={{ fontSize: "1.25rem", fontWeight: 700, letterSpacing: "0.05em" }}>
          JARVIS AI
        </h2>
        <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "0.25rem" }}>
          Local · Open Source
        </p>
      </div>

      <nav style={{ flex: 1, padding: "1rem 0.75rem" }}>
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.75rem",
                padding: "0.75rem 1rem",
                borderRadius: "8px",
                marginBottom: "0.25rem",
                fontSize: "0.95rem",
                fontWeight: isActive ? 600 : 400,
                background: isActive ? "var(--bg-card)" : "transparent",
                color: isActive ? "var(--accent)" : "var(--text-secondary)",
                transition: "all 0.15s",
              }}
            >
              <span style={{ fontSize: "1.1rem" }}>{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div
        style={{
          padding: "1rem 1.5rem",
          borderTop: "1px solid var(--border)",
          fontSize: "0.75rem",
          color: "var(--text-secondary)",
        }}
      >
        Phase 1 · v0.1.0
      </div>
    </aside>
  );
}
