# Format examples

Two worked estimates showing the house format. **The numbers are invented** —
they are here to demonstrate structure and specificity, not to calibrate
anything. Calibration lives in the anchor table in `rubric.md`.

Read these for three things:

- **Shape.** Section headings, where `Assumptions:` sits, `Total (...)` as the
  literal last line, `N/A` for a layer that was considered and not needed.
- **Specificity.** Every line item names a real thing — a service, a table, a
  generator. `Export service following the existing CSV exporter pattern` is a
  line item; `Update the service` is a guess with a number attached.
- **Indentation.** An indented line without hours is a sub-detail of the priced
  item above it, not a line item of its own. Sub-details justify a number, they
  don't subdivide it.

Each entry carries a Redmine issue URL and a `Total (...)` line because
`/calibrate` keys on exactly those two things when it matches an estimate to
the hours logged against its ticket.

**Don't run `/calibrate` against this file.** Only the `/issues/<id>` part of a
URL is read, never the host, so the invented IDs below get looked up against
whatever Redmine profile is active — and if tickets with those numbers happen
to exist, you'll get real time entries for unrelated work.

---

Bulk export for widgets
Task: Allow exporting widgets from the listing screen
Redmine: https://redmine.example.com/issues/12345
Assumptions:
  AI-assisted development. The CSV exporter pattern is treated as shipped and
  reusable. Least confident in the background-job threshold.
Breakdown:
Backend (3.5 hrs)
  Export service following the existing CSV exporter pattern (2 hr)
    Column selection from the list view preference
    Background job for exports over 10k rows
  Controller action, route, ability (0.5 hr)
  Serializer changes for the export payload (0.5 hr)
  Rake task to backfill the export_enabled flag for existing tenants (0.5 hr)
Frontend (2 hrs)
  Export button and format dropdown in the listing toolbar (1 hr)
    Redux slice, action mapper, API method
  Progress toast for background exports (1 hr)
Testing (1 hr)
Demo + PR Reviews (2 hrs)
Total (8.5 hrs ~ 2 points)

Widget audit trail
Task: Track who changed a widget and when
Redmine: https://redmine.example.com/issues/12346
Assumptions:
  AI-assisted development. No frontend surface in scope — the history tab is
  ticket 12350 and is priced there, not here. Retention policy unspecified and
  priced into Discussions.
Breakdown:
Backend (5 hrs)
  Schema change (0.5 hr)
    New table: widget_events
    Columns: widget_id, actor_id, event_type, payload
  Model, associations, validations (0.5 hr)
  Event recording in the widget update path (2 hr)
    Verify every mutation route is covered, not just the controller
  Presenter and serializer for the history tab (1 hr)
  Filters on the existing pattern (1 hr)
Frontend (N/A)
Testing (1 hr)
Demo + PR Reviews (2 hrs)
Discussions + Additional cases: 2 hours
  Retention policy for events was never specified
Total (10 hrs ~ 3 points)
