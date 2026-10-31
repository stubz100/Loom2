// W31: a record's time as the author's clock shows it — the server writes UTC ("…Z"); slicing the string showed 15:15 at 16:15 CET.

/** "2026-10-30 16:15" in local time; the text as it is when it does not read as a time. */
export function localTime(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`)            // a time without a zone is the server's UTC
  if (Number.isNaN(d.getTime())) return iso
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}
