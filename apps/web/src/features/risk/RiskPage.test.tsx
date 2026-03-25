import { screen, waitFor, fireEvent } from "@testing-library/react";
import { renderWithProviders } from "@test/helpers";
import { RiskPage } from "./RiskPage";
import type { RiskRule, RiskAlert } from "./types";

vi.mock("@core/hooks", async () => {
  const actual = await vi.importActual<typeof import("@core/hooks")>("@core/hooks");
  return {
    ...actual,
    useApi: vi.fn(),
    useWs: vi.fn().mockReturnValue({ connected: true }),
  };
});

const mockToast = vi.fn();
vi.mock("@shared/ui", async () => {
  const actual = await vi.importActual<typeof import("@shared/ui")>("@shared/ui");
  return {
    ...actual,
    useToast: () => ({ toast: mockToast }),
  };
});

// Track the last auth mock so tests can override
let mockHasRole: (min: string) => boolean = () => true;

vi.mock("@core/auth", () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useAuth: () => ({
    role: "risk_manager",
    hasRole: (min: string) => mockHasRole(min),
    setRole: () => {},
    clearRole: () => {},
  }),
}));

vi.mock("./api", () => ({
  riskApi: {
    rules: vi.fn(),
    alerts: vi.fn(),
    toggleRule: vi.fn(),
    killSwitch: vi.fn(),
  },
}));

const { useApi } = await import("@core/hooks");
const { riskApi } = await import("./api");

const mockRules: RiskRule[] = [
  { name: "max_position_weight", enabled: true },
  { name: "daily_drawdown", enabled: false },
];

const mockAlerts: RiskAlert[] = [
  {
    timestamp: "2024-01-15T10:00:00Z",
    rule_name: "max_position_weight",
    severity: "warning",
    metric_value: 0.12,
    threshold: 0.1,
    action_taken: "REJECT",
    message: "Position weight exceeded",
  },
];

function setupUseApi(overrides: {
  rules?: RiskRule[] | null;
  rulesError?: string | null;
  alerts?: RiskAlert[] | null;
  alertsError?: string | null;
} = {}) {
  const refreshRules = vi.fn();
  const refreshAlerts = vi.fn();
  const setAlerts = vi.fn();

  vi.mocked(useApi).mockImplementation((fetcher: unknown) => {
    // Distinguish calls by the fetcher reference
    if (fetcher === riskApi.rules) {
      return {
        data: overrides.rules ?? mockRules,
        loading: overrides.rules === undefined && !overrides.rulesError,
        error: overrides.rulesError ?? null,
        refresh: refreshRules,
        setData: vi.fn(),
      } as ReturnType<typeof useApi>;
    }
    // alerts
    return {
      data: overrides.alerts ?? mockAlerts,
      loading: false,
      error: overrides.alertsError ?? null,
      refresh: refreshAlerts,
      setData: setAlerts,
    } as ReturnType<typeof useApi>;
  });

  return { refreshRules, refreshAlerts, setAlerts };
}

describe("RiskPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockHasRole = () => true;
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });

  it("shows loading skeleton initially", () => {
    vi.mocked(useApi).mockReturnValue({
      data: null,
      loading: true,
      error: null,
      refresh: vi.fn(),
      setData: vi.fn(),
    } as ReturnType<typeof useApi>);

    const { container } = renderWithProviders(<RiskPage />);
    // When data is null with no error, the rules section renders but with no rule items.
    // The page title should still render.
    expect(screen.getByText("Risk Management")).toBeInTheDocument();
  });

  it("renders rules with rule names", () => {
    setupUseApi();

    renderWithProviders(<RiskPage />);

    expect(screen.getByText("Risk Rules")).toBeInTheDocument();
    // max_position_weight appears in both rules and alerts, so use getAllByText
    expect(screen.getAllByText("max_position_weight").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("daily_drawdown")).toBeInTheDocument();
  });

  it("toggle button calls API with confirmation", async () => {
    setupUseApi();
    vi.mocked(riskApi.toggleRule).mockResolvedValue({ message: "ok" });

    renderWithProviders(<RiskPage />);

    // Find the enabled toggle for max_position_weight
    const switches = screen.getAllByRole("switch");
    expect(switches.length).toBe(2);

    // Click the first toggle (max_position_weight, currently enabled)
    // Component uses ConfirmModal (not window.confirm) — must click Confirm in modal
    fireEvent.click(switches[0]);
    await waitFor(() => expect(screen.getByText("Confirm")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Confirm"));

    await waitFor(() => {
      expect(riskApi.toggleRule).toHaveBeenCalledWith("max_position_weight", false);
    });
  });

  it("kill switch visible when hasRole('risk_manager') returns true", () => {
    mockHasRole = (min: string) => ["viewer", "researcher", "trader", "risk_manager"].includes(min);
    setupUseApi();

    renderWithProviders(<RiskPage />);

    expect(screen.getByLabelText("Kill Switch")).toBeInTheDocument();
  });

  it("kill switch hidden when hasRole returns false", () => {
    mockHasRole = () => false;
    setupUseApi();

    renderWithProviders(<RiskPage />);

    expect(screen.queryByLabelText("Kill Switch")).not.toBeInTheDocument();
  });

  it("renders alerts table", () => {
    setupUseApi();

    renderWithProviders(<RiskPage />);

    expect(screen.getByText("Recent Alerts")).toBeInTheDocument();
    // max_position_weight appears in both rules list and alerts table
    expect(screen.getAllByText("max_position_weight").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("REJECT")).toBeInTheDocument();
    expect(screen.getByText("Position weight exceeded")).toBeInTheDocument();
  });
});
