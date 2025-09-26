"use client";

import { Button } from "@/components/common/shadcn-components/button";
import { Code, PanelLeftClose, PanelRightClose } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useMemo, useState } from "react";

export default function WorkspaceLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [isCollapsed, setIsCollapsed] = useState(true);
  const pathname = usePathname();

  const navItems = useMemo(() => {
    // Show only basic navigation
    return [{ href: "/workspace", label: "Repositories", icon: Code }];
  }, []);

  return (
    <div className="flex overflow-hidden h-screen">
      <aside
        className={`bg-card border-r border-border transition-all duration-300 ${
          isCollapsed ? "w-16" : "w-64"
        }`}
      >
        <div className="flex flex-col h-full">
          <div className="p-4 flex items-center justify-between">
            {!isCollapsed && <h2 className="text-xl font-bold">Workspace</h2>}
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setIsCollapsed(!isCollapsed)}
            >
              {isCollapsed ? <PanelRightClose /> : <PanelLeftClose />}
            </Button>
          </div>
          <nav className="flex-1 px-2 py-4 space-y-2">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center p-2 rounded-md text-sm font-medium ${
                  pathname === item.href
                    ? "bg-primary text-primary-foreground"
                    : "hover:bg-muted"
                }`}
              >
                <item.icon className="h-5 w-5 mr-3" />
                {!isCollapsed && <span>{item.label}</span>}
              </Link>
            ))}
          </nav>
        </div>
      </aside>
      <main className={`flex-1 overflow-y-auto min-h-0`}>{children}</main>
    </div>
  );
}
