import { extractRoleFromJwt } from "./AuthContext";

// Helper: create a fake JWT with a given payload
function fakeJwt(payload: Record<string, unknown>, useBase64Url = false): string {
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  let body = btoa(JSON.stringify(payload));
  if (useBase64Url) {
    body = body.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }
  return `${header}.${body}.fakesignature`;
}

describe("extractRoleFromJwt", () => {
  it("extracts admin role from standard base64 JWT", () => {
    const token = fakeJwt({ role: "admin", sub: "alice" });
    expect(extractRoleFromJwt(token)).toBe("admin");
  });

  it("extracts trader role", () => {
    const token = fakeJwt({ role: "trader", sub: "bob" });
    expect(extractRoleFromJwt(token)).toBe("trader");
  });

  it("extracts role from base64url-encoded JWT (no padding)", () => {
    const token = fakeJwt({ role: "risk_manager", sub: "carol" }, true);
    expect(extractRoleFromJwt(token)).toBe("risk_manager");
  });

  it("returns viewer for unknown role", () => {
    const token = fakeJwt({ role: "superuser" });
    expect(extractRoleFromJwt(token)).toBe("viewer");
  });

  it("returns viewer when role is missing from payload", () => {
    const token = fakeJwt({ sub: "dave" });
    expect(extractRoleFromJwt(token)).toBe("viewer");
  });

  it("returns viewer for non-JWT string (no dots)", () => {
    expect(extractRoleFromJwt("plain-api-key-1234")).toBe("viewer");
  });

  it("returns viewer for malformed base64", () => {
    expect(extractRoleFromJwt("a.!!!invalid!!!.c")).toBe("viewer");
  });

  it("returns viewer for empty string", () => {
    expect(extractRoleFromJwt("")).toBe("viewer");
  });
});
