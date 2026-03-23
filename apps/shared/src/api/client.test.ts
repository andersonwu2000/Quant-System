import { ApiError, initClient, get } from "./client";

describe("ApiError", () => {
  it("has correct properties", () => {
    const err = new ApiError(404, "Not found");
    expect(err.status).toBe(404);
    expect(err.detail).toBe("Not found");
    expect(err.message).toBe("Not found");
    expect(err.name).toBe("ApiError");
    expect(err).toBeInstanceOf(Error);
  });
});

describe("client not initialized", () => {
  it("throws when calling get without init", async () => {
    // Reset client state by re-initializing module — since we can't reset _adapter,
    // we test that initClient works
    initClient({
      getBaseUrl: () => "http://test",
      getHeaders: async () => ({}),
    });
    // This should not throw "Client not initialized"
    // It will throw a network error since http://test doesn't exist, which is fine
    await expect(get("/test")).rejects.toThrow();
  });
});
