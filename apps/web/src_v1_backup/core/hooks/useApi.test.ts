import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { useApi } from "./useApi";

describe("useApi", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("starts with loading=true and data=null", () => {
    const fetcher = vi.fn(() => new Promise<string>(() => {})); // never resolves
    const { result } = renderHook(() => useApi(fetcher));
    expect(result.current.loading).toBe(true);
    expect(result.current.data).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("fetches data on mount", async () => {
    const fetcher = vi.fn(() => Promise.resolve("hello"));
    const { result } = renderHook(() => useApi(fetcher));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toBe("hello");
    expect(result.current.error).toBeNull();
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("handles fetch error", async () => {
    const fetcher = vi.fn(() => Promise.reject(new Error("fail")));
    const { result } = renderHook(() => useApi(fetcher));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toBeNull();
    expect(result.current.error).toBe("fail");
  });

  it("handles non-Error rejection", async () => {
    const fetcher = vi.fn(() => Promise.reject("string error"));
    const { result } = renderHook(() => useApi(fetcher));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe("Request failed");
  });

  it("supports manual refresh", async () => {
    let count = 0;
    const fetcher = vi.fn(() => Promise.resolve(++count));
    const { result } = renderHook(() => useApi(fetcher));

    await waitFor(() => expect(result.current.data).toBe(1));

    await act(async () => {
      await result.current.refresh();
    });
    expect(result.current.data).toBe(2);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("re-fetches when deps change", async () => {
    let callCount = 0;
    const fetcher = vi.fn(() => Promise.resolve(++callCount));

    const { result, rerender } = renderHook(
      ({ dep }: { dep: string }) => useApi(fetcher, [dep]),
      { initialProps: { dep: "a" } },
    );

    await waitFor(() => expect(result.current.data).toBe(1));

    rerender({ dep: "b" });
    await waitFor(() => expect(result.current.data).toBe(2));
  });

  it("exposes setData for external updates", async () => {
    const fetcher = vi.fn(() => Promise.resolve(42));
    const { result } = renderHook(() => useApi(fetcher));

    await waitFor(() => expect(result.current.data).toBe(42));

    act(() => {
      result.current.setData(100);
    });
    expect(result.current.data).toBe(100);
  });
});
