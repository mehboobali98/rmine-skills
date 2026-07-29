# Calibration samples — format example

**This file is an example, not calibration data.** The numbers below are made up.
Copy the shape into `samples.local.md` (gitignored) with your own real
estimates; the skill reads that file, not this one.

Why it matters: the estimator anchors on the closest comparable past estimate
before it touches the anchor table in `rubric.md`. Real samples are the single
biggest quality lever available, and they're also the reason the file is
gitignored — real estimates name internal services, tickets and customers.

Two things each entry must have, because `/calibrate` keys on them later:

- a **Redmine issue URL**, so estimates can be matched to logged time
- a **`Total (...)` line**, as the last line of the entry

Indentation carries meaning: an indented line without hours is a sub-detail of
the priced item above it, not a line item of its own.

**Don't run `/calibrate` against this file.** Only the `/issues/<id>` part of a
URL is read, never the host, so the invented IDs below get looked up against
whatever Redmine profile is active — and if tickets with those numbers happen to
exist, you'll get real time entries for unrelated work.

---

March'26

Bulk export for widgets
Task: Allow exporting widgets from the listing screen
Redmine: https://redmine.example.com/issues/12345
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
