export function selectValue(e: Event, fallback?: string): string {
  return (e.currentTarget as HTMLSelectElement).value || fallback || '';
}

export function inputInt(e: Event, fallback: number): number {
  const v = parseInt((e.currentTarget as HTMLInputElement).value, 10);
  return isNaN(v) ? fallback : v;
}

export function inputFloat(e: Event, fallback: number): number {
  const v = parseFloat((e.currentTarget as HTMLInputElement).value);
  return isNaN(v) ? fallback : v;
}

export function inputStr(e: Event, fallback?: string): string {
  return (e.currentTarget as HTMLInputElement).value || fallback || '';
}
