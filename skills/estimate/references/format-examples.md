# Format examples

Two worked estimates showing the house format. **The numbers are invented** —
they are here to demonstrate structure and specificity, not to calibrate
anything. Calibration lives in the anchor table in `rubric.md`.

Read these for four things:

- **Shape.** The required header lines, where `Assumptions:` sits,
  `Total (...)` as the literal last line, `N/A` for a layer that was considered
  and not needed. Both entries below pass `scripts/check_format.py`; run it on
  anything you write.
- **Nesting.** A numbered outline — `1.` for sections, `a.` for line items,
  `i.` and deeper for sub-details. This is what a Google Doc produces, and the
  level a line sits at is what says whether it's a section, a priced item, or
  the justification for one. A plain two-space indent with no markers reads
  identically to the tooling; what must not happen is flattening, which throws
  the structure away.
- **Specificity.** Every line item names a real thing — a service, a table, a
  generator. `Export service following the existing CSV exporter pattern` is a
  line item; `Update the service` is a guess with a number attached.
- **Unpriced line items.** `2.b` in the second entry carries no hours. It
  describes what the section covers rather than claiming a slice of it, and its
  priced siblings still sum to the section — so nothing hides behind it.

The non-development lines differ between the two on purpose: the first entry is
under ~10 hrs, so Testing collapses into `Demo + PR Reviews + Testing`; the
second is over, so Testing stands alone at roughly 10–15% of dev hours. Both
rules are in `rubric.md`.

Note how `Confidence` differs between the two, and that neither is a bare
grade — the reason is the part a reader can act on.

Each entry carries a Redmine issue URL and a `Total (...)` line because
`/calibrate` keys on exactly those two things when it matches an estimate to
the hours logged against its ticket.

**Don't run `/calibrate` against this file.** Only the `/issues/<id>` part of a
URL is read, never the host, so the invented IDs below get looked up against
whatever Redmine profile is active — and if tickets with those numbers happen
to exist, you'll get real time entries for unrelated work.

---

**Task**: Allow exporting widgets from the listing screen
**Redmine**: https://redmine.example.com/issues/12345
**Estimated by**: A. Engineer
**Date**: 2026-03-04
**Confidence**: High — every line item priced from a matching anchor row against
  the existing CSV exporter pattern
**Assumptions**:
    AI-assisted development. The CSV exporter pattern is treated as shipped and
    reusable. Least confident in the background-job threshold.
**Breakdown**:
    1. Backend (3.5 hrs)
        a. Export service following the existing CSV exporter pattern (2 hr)
            i. Column selection from the list view preference
            ii. Background job for exports over 10k rows
        b. Controller action, route, ability (0.5 hr)
        c. Serializer changes for the export payload (0.5 hr)
        d. Rake task to backfill the export_enabled flag for existing tenants (0.5 hr)
    2. Frontend (2 hrs)
        a. Export button and format dropdown in the listing toolbar (1 hr)
            i. Redux slice, action mapper, API method
        b. Progress toast for background exports (1 hr)
    3. Demo + PR Reviews + Testing (3 hrs)
    4. Total (8.5 hrs ~ 2 points)

**Task**: Track who changed a widget and when
**Redmine**: https://redmine.example.com/issues/12346
**Estimated by**: A. Engineer
**Date**: 2026-03-06
**Confidence**: Medium — the retention policy is unspecified and priced into
  Discussions rather than calibrated
**Assumptions**:
    AI-assisted development. No frontend surface in scope — the history tab is
    ticket 12350 and is priced there, not here. Retention policy unspecified and
    priced into Discussions.
**Breakdown**:
    1. Backend (7 hrs)
        a. Schema change (0.5 hr)
            i. New table: widget_events
            ii. Columns: widget_id, actor_id, event_type, payload
        b. Model, associations, validations (0.5 hr)
        c. Event recording in the widget update path (2 hr)
            i. Verify every mutation route is covered, not just the controller
                1. WidgetsController, the bulk update path, and the importer
        d. Presenter and serializer for the history tab (1 hr)
        e. Filters on the existing pattern (1 hr)
        f. Ability and permission checks on the history endpoint (2 hr)
    2. Frontend (N/A)
    3. Testing (1 hr)
    4. Demo + PR Reviews (2 hrs)
    5. Discussions + Additional cases: 2 hours
        a. Retention policy for events was never specified
    6. Total (12 hrs ~ 3 points)
