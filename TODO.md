# UI Improvements Backlog

## Medium Priority

- [ ] **No scroll indicators on list cards** — List cards with `overflow-y: auto` don't signal that more items exist below the fold. Add a bottom fade/shadow when content overflows.

- [ ] **Calendar week columns don't handle event overflow** — A day with 8+ events stretches the column, pushing the month view off screen. Add a max-height with internal scroll or a "+N more" indicator.

- [ ] **Budget bars cap at 100% with no overage indicator** — When over budget, the bar turns red but stays full. Can't tell if $5 or $500 over. Show overage amount or extend the bar past 100%.

## Low Priority

- [ ] **Weekend plans always prominent** — "Weekend Plans" card takes right-column space even on Monday. Consider collapsing or de-emphasizing on weekdays.

- [ ] **Tab switch re-renders entire DOM** — Every switch rebuilds all content even when data hasn't changed. Check if data is stale before re-rendering to eliminate flicker.

- [ ] **Keyboard has no cursor positioning** — `kbBuffer` only supports append/backspace. No way to tap into preview text to edit mid-word. Minor for short list items, noticeable for message board text.
