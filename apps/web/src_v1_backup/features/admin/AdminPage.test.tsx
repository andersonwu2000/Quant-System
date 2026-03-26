import { screen, waitFor, fireEvent } from "@testing-library/react";
import { renderWithProviders } from "@test/helpers";
import { AdminPage } from "./AdminPage";
import type { UserInfo } from "@core/api";

vi.mock("@core/hooks", async () => {
  const actual = await vi.importActual<typeof import("@core/hooks")>("@core/hooks");
  return {
    ...actual,
    useApi: vi.fn(),
  };
});

vi.mock("@core/auth", () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useAuth: () => ({
    role: "admin",
    hasRole: (min: string) => ["viewer", "researcher", "trader", "risk_manager", "admin"].includes(min),
    setRole: () => {},
    clearRole: () => {},
  }),
}));

const mockToast = vi.fn();
vi.mock("@shared/ui", async () => {
  const actual = await vi.importActual<typeof import("@shared/ui")>("@shared/ui");
  return {
    ...actual,
    useToast: () => ({ toast: mockToast }),
  };
});

vi.mock("./api", () => ({
  adminApi: {
    listUsers: vi.fn(),
    createUser: vi.fn(),
    updateUser: vi.fn(),
    deleteUser: vi.fn(),
    resetPassword: vi.fn(),
  },
}));

const { useApi } = await import("@core/hooks");
const { adminApi } = await import("./api");

const mockUsers: UserInfo[] = [
  {
    id: 1,
    username: "alice",
    display_name: "Alice Chen",
    role: "admin",
    is_active: true,
    failed_login_count: 0,
    locked_until: null,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  },
  {
    id: 2,
    username: "bob",
    display_name: "Bob Wang",
    role: "trader",
    is_active: true,
    failed_login_count: 0,
    locked_until: null,
    created_at: "2024-01-10T00:00:00Z",
    updated_at: "2024-01-10T00:00:00Z",
  },
];

function setupUseApi(overrides: {
  users?: UserInfo[] | null;
  loading?: boolean;
  error?: string | null;
} = {}) {
  const refresh = vi.fn();
  vi.mocked(useApi).mockReturnValue({
    data: overrides.users ?? mockUsers,
    loading: overrides.loading ?? false,
    error: overrides.error ?? null,
    refresh,
    setData: vi.fn(),
  } as ReturnType<typeof useApi>);
  return { refresh };
}

describe("AdminPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });

  it("shows loading state initially", () => {
    setupUseApi({ users: null, loading: true });

    renderWithProviders(<AdminPage />);

    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("renders users table with usernames", () => {
    setupUseApi();

    renderWithProviders(<AdminPage />);

    expect(screen.getByText("User Management")).toBeInTheDocument();
    expect(screen.getByText("alice")).toBeInTheDocument();
    expect(screen.getByText("bob")).toBeInTheDocument();
    expect(screen.getByText("Alice Chen")).toBeInTheDocument();
    expect(screen.getByText("Bob Wang")).toBeInTheDocument();
  });

  it("shows error alert on API failure", () => {
    setupUseApi({ error: "Forbidden" });

    renderWithProviders(<AdminPage />);

    expect(screen.getByText("User Management")).toBeInTheDocument();
    expect(screen.getByText("Forbidden")).toBeInTheDocument();
  });

  it("create user button opens modal", async () => {
    setupUseApi();

    renderWithProviders(<AdminPage />);

    const addButton = screen.getByText("Add User");
    fireEvent.click(addButton);

    await waitFor(() => {
      // Modal should show form fields — use getAllByText since "Username" also
      // appears as a table column header rendered by DataTable.
      const usernameLabels = screen.getAllByText("Username");
      expect(usernameLabels.length).toBeGreaterThanOrEqual(2); // table header + modal label
      expect(screen.getByText("Password")).toBeInTheDocument();
    });
  });

  it("prevents deleting the last active admin", async () => {
    setupUseApi();

    renderWithProviders(<AdminPage />);

    // deleteButtons[0] = alice (only admin) — should be blocked
    const deleteButtons = screen.getAllByTitle("Delete User");
    fireEvent.click(deleteButtons[0]);

    expect(mockToast).toHaveBeenCalledWith("error", "Cannot delete the last active admin");
    expect(window.confirm).not.toHaveBeenCalled();
    expect(adminApi.deleteUser).not.toHaveBeenCalled();
  });

  it("delete non-admin triggers confirmation and API call", async () => {
    setupUseApi();
    vi.mocked(adminApi.deleteUser).mockResolvedValue({ message: "deleted" });

    renderWithProviders(<AdminPage />);

    // deleteButtons[1] = bob (trader) — should proceed normally
    const deleteButtons = screen.getAllByTitle("Delete User");
    // Component uses ConfirmModal (not window.confirm) — must click Confirm in modal
    fireEvent.click(deleteButtons[1]);
    await waitFor(() => expect(screen.getByText("Confirm")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Confirm"));

    await waitFor(() => {
      expect(adminApi.deleteUser).toHaveBeenCalledWith(2);
    });
  });
});
