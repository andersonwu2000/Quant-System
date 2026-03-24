import { useState } from "react";
import { useT } from "@core/i18n";
import { TabBar } from "@shared/ui";
import { PortfolioPage } from "@feat/portfolio";
import { OrdersPage } from "@feat/orders";
import { PaperTradingPage } from "@feat/paper-trading";

type Tab = "portfolio" | "orders" | "paper-trading";

export function TradingPage() {
  const { t } = useT();
  const [tab, setTab] = useState<Tab>("portfolio");

  const tabs: { id: Tab; label: string }[] = [
    { id: "portfolio", label: t.nav.portfolio },
    { id: "orders", label: t.nav.orders },
    { id: "paper-trading", label: t.nav.paperTrading },
  ];

  return (
    <div className="space-y-6">
      {/* Tab bar */}
      <TabBar tabs={tabs} active={tab} onChange={setTab} />

      {/* Tab content */}
      {tab === "portfolio" && <PortfolioPage />}
      {tab === "orders" && <OrdersPage />}
      {tab === "paper-trading" && <PaperTradingPage />}
    </div>
  );
}
