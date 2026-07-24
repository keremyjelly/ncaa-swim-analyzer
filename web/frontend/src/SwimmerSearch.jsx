import { useEffect, useMemo, useRef, useState } from "react";

/**
 * Searchable swimmer picker, shared by Swimmer Trends and Head-to-Head.
 *
 * Replaces a 600-entry <select> / prefix-only <datalist>. Two ways to narrow:
 *
 *   - a Team dropdown, and
 *   - flexible typing, where the query is split into tokens and EVERY token has
 *     to appear somewhere in "name + schools". Names are stored "Last, First",
 *     so plain substring matching fails on natural input — tokens fix that:
 *
 *         "josh liendo"  -> Liendo, Josh      (tokens match across the comma)
 *         "li flor"      -> Liendo, Josh · Florida
 *         "texas"        -> every Texas swimmer
 *
 * Ranking prefers a last-name prefix, then a first-name prefix, then anything
 * else, so typing "car" surfaces Carr before Mccarty.
 */

// Fold accents and lowercase, so "Bjorn" finds "Björn".
const norm = (s) =>
  (s ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "") // strip combining marks left by NFD
    .toLowerCase();

function score(item, tokens) {
  const last = norm(item.name.split(",")[0]);
  const first = norm(item.name.split(",")[1] ?? "");
  // Former spellings are searchable too: a swimmer listed as "Caribe,
  // Guilherme" through 2025 and "Caribe, Gui" in 2026 is one entry, and typing
  // either form has to find them.
  const hay = [
    norm(item.name),
    norm((item.schools ?? []).join(" ")),
    norm((item.also_known_as ?? []).join(" ")),
  ].join(" ");

  let best = 0;
  for (const t of tokens) {
    if (!hay.includes(t)) return -1; // every token must hit somewhere
    if (last.startsWith(t)) best = Math.max(best, 3);
    else if (first.trim().startsWith(t)) best = Math.max(best, 2);
    else best = Math.max(best, 1);
  }
  return best;
}

export default function SwimmerSearch({
  items,
  value,
  onChange,
  label,
  placeholder = "Type a name or team…",
  id,
  renderMeta,
  autoFocus = false,
}) {
  const [query, setQuery] = useState("");
  const [team, setTeam] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const boxRef = useRef(null);
  const listRef = useRef(null);

  const teams = useMemo(() => {
    const set = new Set();
    items.forEach((s) => (s.schools ?? []).forEach((x) => set.add(x)));
    return [...set].sort((a, b) => a.localeCompare(b));
  }, [items]);

  // A team filter that no longer matches (event or gender changed) would
  // silently show an empty list, so drop it.
  useEffect(() => {
    if (team && !teams.includes(team)) setTeam("");
  }, [teams, team]);

  const matches = useMemo(() => {
    const tokens = norm(query).split(/\s+/).filter(Boolean);
    const pool = team ? items.filter((s) => (s.schools ?? []).includes(team)) : items;
    if (!tokens.length) return pool.slice(0, 200);
    return pool
      .map((s) => ({ s, r: score(s, tokens) }))
      .filter((x) => x.r > 0)
      .sort((a, b) => b.r - a.r || a.s.name.localeCompare(b.s.name))
      .slice(0, 200)
      .map((x) => x.s);
  }, [items, query, team]);

  useEffect(() => setActive(0), [query, team]);

  // Keep the highlighted row in view during keyboard navigation.
  useEffect(() => {
    if (!open || !listRef.current) return;
    const el = listRef.current.children[active];
    if (el) el.scrollIntoView({ block: "nearest" });
  }, [active, open]);

  useEffect(() => {
    const onDoc = (e) => {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const commit = (s) => {
    onChange(s.name);
    setQuery("");
    setOpen(false);
  };

  const onKeyDown = (e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      setOpen(true);
      setActive((i) => {
        const n = matches.length;
        if (!n) return 0;
        return e.key === "ArrowDown" ? (i + 1) % n : (i - 1 + n) % n;
      });
    } else if (e.key === "Enter") {
      if (open && matches[active]) {
        e.preventDefault();
        commit(matches[active]);
      }
    } else if (e.key === "Escape") {
      setOpen(false);
      setQuery("");
    }
  };

  return (
    <div className="swsearch" ref={boxRef}>
      {label && <label htmlFor={id}>{label}</label>}

      <div className="swsearch-row">
        <input
          id={id}
          className="swsearch-input"
          value={open ? query : value ?? ""}
          placeholder={value ? value : placeholder}
          autoFocus={autoFocus}
          onFocus={() => { setQuery(""); setOpen(true); }}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
          onKeyDown={onKeyDown}
          role="combobox"
          aria-expanded={open}
          aria-autocomplete="list"
        />
        {teams.length > 1 && (
          <select
            className="swsearch-team"
            value={team}
            onChange={(e) => setTeam(e.target.value)}
            aria-label="Filter by team"
          >
            <option value="">All teams</option>
            {teams.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        )}
      </div>

      {open && (
        <div className="swsearch-pop">
          <div className="swsearch-count">
            {matches.length === 0
              ? "no swimmers match"
              : `${matches.length}${matches.length === 200 ? "+" : ""} of ${items.length}`}
          </div>
          <ul className="swsearch-list" ref={listRef} role="listbox">
            {matches.map((s, i) => (
              <li
                key={s.name}
                role="option"
                aria-selected={i === active}
                className={i === active ? "swsearch-opt active" : "swsearch-opt"}
                onMouseEnter={() => setActive(i)}
                onMouseDown={(e) => { e.preventDefault(); commit(s); }}
              >
                <span className="swsearch-name">
                  {s.name}
                  {(s.also_known_as ?? []).length > 0 && (
                    <span className="swsearch-aka">
                      {" "}aka {s.also_known_as.map((n) => n.split(",")[1]?.trim() ?? n).join(", ")}
                    </span>
                  )}
                </span>
                <span className="swsearch-meta">
                  {renderMeta ? renderMeta(s) : (s.schools ?? []).join(" / ")}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
