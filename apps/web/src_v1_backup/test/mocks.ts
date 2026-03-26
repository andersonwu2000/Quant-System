export function mockApi<T>(data: T) {
  return vi.fn().mockResolvedValue(data);
}

export function mockApiError(message: string) {
  return vi.fn().mockRejectedValue(new Error(message));
}
