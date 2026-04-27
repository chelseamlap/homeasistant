# Chore Widget & Today Tab Redesign

## Summary

Redesign the Today tab layout and add a dedicated chore widget with per-person swim lanes. Also merges the two separate calendar views into one unified 7-day strip, replaces the weekend plans widget with a sticky-note-styled Notes card, and surfaces more Todoist data (description, labels) in list items.

## Motivation

Chores currently live in Chelsea's head and don't get distributed. The existing list UI doesn't make ownership or timing visible at a glance. The dashboard needs a dedicated chore view that makes it obvious who needs to do what and when.

## Today Tab Layout

### Current Layout (two columns)
```
LEFT                          RIGHT
- Weather + Notes (row)       - Today's Schedule
- Today Lists (show_on_today) - Weekend Plans (Sat/Sun fields)
                              - Next 5 Days
```

### New Layout (three columns + full-width bottom)
```
LEFT                CENTER              RIGHT
- Weather           - Today Lists       - 7-Day Calendar
- Sticky Note         (show_on_today)     (unified, today emphasized)

FULL WIDTH BOTTOM
- Chores Widget (swim lanes: Chelsea | Husband | Home)
```

### Key Changes
1. **Calendar merged**: "Today's Schedule" and "Next 5 Days" become one 7-day calendar strip. Today is visually emphasized (accent border, bold, background highlight). Every day shown even if empty ("No events" in italic).
2. **Weekend Plans removed**: The Saturday/Sunday intention fields are removed entirely. The Notes card is pre-seeded with "What should we do this weekend?" to serve the same purpose.
3. **Notes becomes a sticky note**: Yellow background (#fff9c4), faux tape strip, slight rotation (-0.5deg), warm brown text (#5d4037). Feels like a note on the fridge.
4. **Column order**: Weather+Sticky (left) | Today Lists (center) | Calendar (right). Calendar on the right follows the Gmail/Outlook convention.

## Chore Widget

### Data Source
- Todoist project (configurable via settings, e.g. `chores_list` key)
- Uses existing Todoist integration — no new backend needed
- Only shows items due in the next 14 days (filter by `due_date`)

### Swim Lanes
Three columns determined by assignee:
- **Chelsea** (purple, #9c27b0) — items assigned to Chelsea
- **Husband** (blue, #2196f3) — items assigned to husband
- **Home** (gray, --text-dim) — unassigned items (anyone can do them)

Lane headers have the person's name in their color with a colored bottom border.

### Item Display
Each chore row shows:
- Checkbox circle (same style as existing list rows)
- **Title** in normal text
- **Description** in dimmed text below title (always visible, not expandable)
- **Due bucket** aligned right: "Today" (orange, bold), "This week", "Next week"

### Due Date Buckets
Instead of specific dates, chores show coarse time buckets:
- **Today**: due date is today (styled in --orange, font-weight 600)
- **This week**: due date is within the current week
- **Next week**: due date is in the following week
- Items due beyond 14 days are not shown

### Interaction
- **Tap anywhere on the row** to mark complete (same as existing list behavior)
- Completed items fade to bottom of lane with reduced opacity
- Undo toast appears for 3 seconds (existing behavior)
- No expand, no popup, no extra taps

### Completed Items
Same collapsible "Completed (N)" divider as existing lists, per lane.

## Unified Calendar

### Behavior
- Shows 7 days starting from today
- **Today** gets: accent-colored left border, subtle background highlight, "Today" label instead of day name, bold text
- **Other days** show: day abbreviation + date (e.g. "Mon Apr 28"), events listed below
- **Empty days** show "No events" in italic dimmed text
- Events show time (accent color, bold) + summary, same as current event rendering
- Guest/visitor indicators preserved (--visitor color)

### API Changes
- New endpoint or modified `/api/calendar/week` that returns 7 days starting from today, including today's events and empty days
- Returns all days even if they have no events

## Sticky Note (Notes Widget)

### Visual Style
- Background: #fff9c4 (warm yellow)
- Text: #5d4037 (warm brown)
- Faux tape strip centered on top edge
- Slight rotation: transform rotate(-0.5deg)
- Subtle box shadow for depth
- Each note separated by faint bottom border
- **Theme-independent**: sticky note always looks yellow regardless of dark/light/warm theme

### Behavior
- Same add/delete/edit functionality as current Notes
- Pre-seeded with "What should we do this weekend?" on first load (if no notes exist)

## List Item Enhancements (already implemented)

These changes apply to all list views (Today tab lists, Lists tab):
- **Description**: shown as dimmed second line under title (truncated with ellipsis)
- **Labels**: shown as gray pills next to assignee/due date
- **Assignee colors**: Chelsea = purple (#9c27b0), everyone else = blue (#2196f3)

## Settings

New settings fields needed:
- `chores_list`: key of the Todoist project to use for the chore widget (e.g. "chores")
- `chore_people`: map of assignee name patterns to colors and display names, e.g.:
  ```json
  {
    "chelsea": {"color": "#9c27b0", "label": "Chelsea"},
    "_default": {"color": "#2196f3", "label": "Husband"}
  }
  ```
- `chore_unassigned_label`: display name for the unassigned lane (default: "Home")

## Files to Modify

- `templates/index.html` — Today tab HTML restructure, new chore widget markup, sticky note CSS, unified calendar renderer, remove weekend plans
- `server/todoist.py` — already updated with description/labels fields
- `server/weather.py` — already updated with null-safety and caching
- `app.py` — new `/api/chores` endpoint (or reuse `/api/reminders/<key>` with filtering), modify calendar endpoint for 7-day unified view
- `server/google_calendar.py` — return 7 days including empty days

## Out of Scope

- Managing chores from the dashboard (add/edit/reassign) — Todoist is the system of record
- Recurring chore auto-creation — handled by Todoist's recurring task feature
- Progress tracking or gamification — this is not a competition
- Comments from Todoist — description field covers the use case
