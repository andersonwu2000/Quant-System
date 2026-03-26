const PW_PATTERN = /^[a-zA-Z0-9]+$/;

export function isValidPassword(pw: string): boolean {
  return pw.length >= 8 && PW_PATTERN.test(pw);
}
