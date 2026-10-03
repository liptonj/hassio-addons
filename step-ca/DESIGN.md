---
name: Step CA SCEP Server
description: A private certificate authority panel that is a native Home Assistant Settings page and wears the user's live HA theme.
colors:
  primary: "#03a9f4"
  accent-fill: "#0273a6"
  accent-ink: "#0270a1"
  accent-ink-dark: "#30b8f6"
  success: "#4caf50"
  warning: "#ff9800"
  error: "#db4437"
  info: "#039be5"
  danger-fill: "#bc3a2f"
  ok-ink: "#327435"
  warn-ink: "#945800"
  warn-ink-dark: "#ffa219"
  bad-ink: "#912d24"
  bad-ink-dark: "#e1665b"
  info-ink: "#026697"
  background: "#fafafa"
  background-dark: "#111111"
  card: "#ffffff"
  card-dark: "#1c1c1c"
  secondary-background: "#e5e5e5"
  secondary-background-dark: "#282828"
  text: "#212121"
  text-dark: "#e1e1e1"
  text-secondary: "#616161"
  text-secondary-dark: "#9b9b9b"
  divider: "rgba(0, 0, 0, 0.12)"
  divider-dark: "rgba(225, 225, 225, 0.12)"
  outline: "rgba(33, 33, 33, 0.54)"
  outline-dark: "rgba(225, 225, 225, 0.54)"
  hover: "rgba(33, 33, 33, 0.05)"
  hover-dark: "rgba(225, 225, 225, 0.05)"
  toast: "#323232"
typography:
  headline:
    fontFamily: "Roboto, Noto Sans, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "24px"
    fontWeight: 400
    lineHeight: "32px"
  dialog-headline:
    fontFamily: "Roboto, Noto Sans, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "22px"
    fontWeight: 400
    lineHeight: "28px"
  title:
    fontFamily: "Roboto, Noto Sans, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "20px"
    fontWeight: 400
    lineHeight: "28px"
  title-small:
    fontFamily: "Roboto, Noto Sans, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "16px"
    fontWeight: 500
    lineHeight: "24px"
  body:
    fontFamily: "Roboto, Noto Sans, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: "20px"
    letterSpacing: "0.01em"
  label:
    fontFamily: "Roboto, Noto Sans, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "14px"
    fontWeight: 500
    lineHeight: "20px"
    letterSpacing: "0.02em"
  caption:
    fontFamily: "Roboto, Noto Sans, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: "16px"
  mono:
    fontFamily: "ui-monospace, SF Mono, Roboto Mono, Menlo, Consolas, monospace"
    fontSize: "13px"
    fontWeight: 400
rounded:
  bar: "3px"
  field: "8px"
  card: "12px"
  chip: "12px"
  button: "20px"
  search: "22px"
  dialog: "28px"
  full: "50%"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  2xl: "32px"
  3xl: "48px"
components:
  button-filled:
    backgroundColor: "{colors.accent-fill}"
    textColor: "#ffffff"
    typography: "{typography.label}"
    rounded: "{rounded.button}"
    padding: "0 20px"
    height: "40px"
  button-text:
    backgroundColor: "transparent"
    textColor: "{colors.accent-ink}"
    typography: "{typography.label}"
    rounded: "{rounded.button}"
    padding: "0 12px"
    height: "40px"
  button-danger:
    backgroundColor: "{colors.danger-fill}"
    textColor: "#ffffff"
    typography: "{typography.label}"
    rounded: "{rounded.button}"
    padding: "0 20px"
    height: "40px"
  button-text-danger:
    backgroundColor: "transparent"
    textColor: "{colors.bad-ink}"
    rounded: "{rounded.button}"
    padding: "0 12px"
    height: "40px"
  icon-button:
    backgroundColor: "transparent"
    textColor: "{colors.text-secondary}"
    rounded: "{rounded.full}"
    size: "36px"
  icon-button-hover:
    backgroundColor: "{colors.hover}"
    textColor: "{colors.text}"
  input:
    backgroundColor: "{colors.card}"
    textColor: "{colors.text}"
    typography: "{typography.body}"
    rounded: "{rounded.field}"
    padding: "10px 12px"
    height: "44px"
  input-search:
    backgroundColor: "{colors.card}"
    textColor: "{colors.text}"
    rounded: "{rounded.search}"
    padding: "10px 12px 10px 42px"
    height: "44px"
  card:
    backgroundColor: "{colors.card}"
    textColor: "{colors.text}"
    rounded: "{rounded.card}"
  card-dark:
    backgroundColor: "{colors.card-dark}"
    textColor: "{colors.text-dark}"
    rounded: "{rounded.card}"
  toolbar:
    backgroundColor: "{colors.background}"
    textColor: "{colors.text}"
    typography: "{typography.title}"
    height: "56px"
  tab:
    textColor: "{colors.text-secondary}"
    typography: "{typography.label}"
    padding: "0 20px"
  tab-active:
    textColor: "{colors.accent-ink}"
  filter-chip:
    backgroundColor: "transparent"
    textColor: "{colors.text}"
    typography: "{typography.label}"
    rounded: "{rounded.field}"
    padding: "0 12px"
    height: "32px"
  status-chip:
    typography: "{typography.caption}"
    rounded: "{rounded.chip}"
    padding: "0 10px 0 8px"
    height: "24px"
  settings-row:
    padding: "12px 16px"
    height: "64px"
  expansion-summary:
    padding: "12px 16px"
    height: "56px"
  copy-field:
    backgroundColor: "{colors.secondary-background}"
    rounded: "{rounded.field}"
    padding: "6px 6px 6px 14px"
    height: "48px"
  dialog:
    backgroundColor: "{colors.card}"
    textColor: "{colors.text}"
    rounded: "{rounded.dialog}"
    padding: "24px"
    width: "min(440px, calc(100vw - 32px))"
  toast:
    backgroundColor: "{colors.toast}"
    textColor: "#f1f1f1"
    rounded: "{rounded.field}"
    padding: "14px 20px"
---

# Design System: Step CA SCEP Server

## Overview

**Creative North Star: "The Settings Page That Was Always There"**

The panel is a native Home Assistant Settings subpage, played straight at Home Assistant's own craft level. It borrows HA's theme custom properties, its Material Design Icons, and the shapes of its own components (hass-tabs-subpage toolbar, ha-card, ha-data-table, ha-settings-row, ha-expansion-panel, ha-alert, ha-dialog). An admin opening it from the sidebar should not be able to find the seam. Inside the HA frame a small script reads the parent document's computed theme variables and copies them onto this page, watching for theme changes, so a custom HA theme recolors the panel live. Outside the frame the page carries HA's own default light and dark values and follows `prefers-color-scheme`.

Density is Settings-page density: 14px body text, 56–64px rows, outlined cards on a flat page background, a 3:2 two-column grid that collapses to one column. Depth comes from 1px divider outlines and tonal tints, not from shadows. Trust data (fingerprints, serials, URLs, validity) is set in monospace and always sits next to a copy action. Reference material stays collapsed in expansion panels until it is needed.

Motion is small and functional: 150ms state transitions on hover and border, a 200ms chevron rotation on expansion panels, and the panel's one authored motion, the copy toast rising and the confirm dialog scaling in on an exponential ease-out. Reduced motion turns the dialog animation, the toast transition, and the chevron rotation off.

**Key Characteristics:**
- HA custom properties are the only palette; the parent theme overrides them live.
- Light and dark modes, chosen by the parent theme's luminance in the frame and by `prefers-color-scheme` outside it.
- Outlined, flat 12px cards; shadows only on the dialog, the toast, and a filled button on hover.
- MDI icons inlined as SVG paths at 24px (20px in tabs and icon buttons, 18px in buttons and chips).
- Two weights (400 and 500), Roboto stack, monospace kept for literal machine values.
- Mobile moves the tabs into a fixed 56px bottom bar.

## Colors

A neutral HA canvas with one theme accent (HA light blue by default) and four status colors. Every themed color drawn as text or behind white text passes through a contrast mix.

### Primary
- **HA Light Blue** (primary): the theme accent. Used raw only where it carries no text: the active-tab underline, the validity bar fill, radio and checkbox accents, caret, and the 6–16% tints behind selected choices, selected filters, step counters, and tile icons. A user's HA theme replaces it.
- **Deep Accent Fill** (accent-fill): the background of filled buttons, 68% primary mixed toward black so white label text holds 4.5:1 for any theme accent.
- **Accent Ink** (accent-ink, accent-ink-dark): links, text buttons, the active tab label, choice icons. Primary mixed 66% toward black in light mode and 82% toward white in dark mode. The shared focus alias (`--focus-color`) follows accent ink for visible outlines, field borders and rings, and linked-table-row indicators.

### Status
- **Success Green** (success), **Warning Orange** (warning), **Error Red** (error), **Info Blue** (info): HA's status colors. Used as the dot inside a status chip, as 12–16% tints behind chips, alerts, and tiles, and never as a text color directly.
- **Status Inks** (ok-ink, warn-ink, bad-ink, info-ink, with dark variants): the foreground of chips, alert icons, tile icons, relative-time warnings, and the danger-zone heading. Each is its status color mixed toward black (light) or white (dark). Warning gets a stronger mix (58% toward black, 90% toward white) because orange is light.
- **Danger Fill** (danger-fill): the filled destructive button (Revoke), error red mixed 86% toward black.

### Neutral
- **Page Gray** (background, background-dark): the page and the toolbar.
- **Card White / Card Charcoal** (card, card-dark): cards, inputs, and the dialog.
- **Recessed Gray** (secondary-background, secondary-background-dark): copy fields and the validity track; a well below the card plane.
- **Ink / Secondary Ink** (text, text-secondary, and dark variants): body text, then labels, table headers, hints, row subtitles, and inactive tabs.
- **Divider** (divider, divider-dark): card outlines, row separators, table rules, toolbar edge.
- **Outline** (outline, outline-dark): input, choice, and filter-chip borders; 28% of the text color.
- **Hover Wash** (hover, hover-dark): 5% of the text color behind any hovered row, tab, summary, or icon button.
- **Snackbar Charcoal** (toast): the copy toast, fixed in both modes like HA's own snackbar.

### Named Rules
**The Borrowed Theme Rule.** Every color comes from an HA custom property (`--primary-color`, `--primary-background-color`, `--card-background-color`, `--primary-text-color`, `--secondary-text-color`, `--divider-color`, the four status colors) or a `color-mix()` of them. The only fixed values are the toast, the white QR backing, the dialog scrim, and white text on filled buttons.

**The Mixed Ink Rule.** A theme color is never used raw as text or as a fill behind text. Use the ink tokens for text and the fill tokens for button backgrounds; they exist so a custom theme's accent stays legible.

**The Tint-Not-Fill Rule.** Status is shown as a 12–16% tint with an ink-mixed foreground (chips, alerts, tiles). Solid status fills are reserved for the destructive button.

## Typography

**Body Font:** Roboto (with Noto Sans, system-ui, -apple-system, Segoe UI, sans-serif)
**Mono Font:** ui-monospace (with SF Mono, Roboto Mono, Menlo, Consolas, monospace)

**Character:** Home Assistant's own type, used plainly. Headings stay at regular weight and get hierarchy from size alone. Medium weight is for labels, titles in lists, and emphasis.

### Hierarchy
- **Headline** (400, 24px, 32px): page heading, certificate name on the detail page, public page heading.
- **Dialog Headline** (400, 22px, 28px): confirm dialog title.
- **Title** (400, 20px, 28px): card headers, the toolbar title (24px line).
- **Title Small** (500, 16px, 24px): choice-card titles, tile values, the MDM form heading. Expansion-panel summary titles use the same size at 400.
- **Body** (400, 14px, 20px, 0.01em): everything else. Card descriptions are capped at 72ch.
- **Label** (500, 14px, 0.02em): form labels, tabs, buttons, filter chips, table headers, the Downloads subhead (in secondary ink).
- **Caption** (400, 12px, 16px): hints, mobile key labels in key-value rows, bottom-bar tab labels. Status chips use it at 500 with 0.02em.
- **Mono** (400, 13px): serials, fingerprints, URLs, subject DNs, extensions, PEM text areas. The one-time password is set larger (22px, 32px line, 0.08em; 18px on mobile).

### Named Rules
**The Two Weights Rule.** Only 400 and 500. `<b>` renders at 500. No bold, no light.

**The Machine Literal Rule.** Monospace is for values a machine reads or a person copies character by character: serials, fingerprints, URLs, distinguished names, extensions, PEM, passwords. Add-on option names in prose are set in medium weight, not monospace.

**The Tabular Rule.** Dates, times, table cells, and validity labels use tabular numerals.

## Layout

Content sits in a centered column below a sticky 56px toolbar: 1120px wide for list, Authority, and Settings pages, 760px for narrow forms, 520px for public enrollment pages. Page padding is 24px sides and 48px bottom on desktop, 16px/12px/32px on mobile. Cards stack with 16px between them.

Two-column pages use a 3fr/2fr grid with a 16px gap, the primary task on the left and reference on the right. At 860px and below the grid becomes one column and the four-tile health card becomes a 2×2 grid. At 640px and below the tabs leave the toolbar and become a fixed 56px bottom bar (icon over a 12px label, active indicator on top), the body reserves 64px at the bottom, form rows and the revoke form go single-column, and key-value rows stack the key above the value. Cards are also container-query hosts: a key-value row stacks below 520px of card width on any screen.

Spacing steps through 4, 8, 12, 16, 24, 32, and 48px. 16px is the default inset for card content, rows, and summaries; 12px is the gap inside rows and alerts; 8px separates related controls.

### Named Rules
**The Progressive Reference Rule.** The common job is open; reference values sit in collapsed expansion panels inside a card. A URL hash naming a panel's id opens it. The six tool pages use persistent navigation so admins can switch tasks directly.

## Elevation & Depth

Flat by default. Cards lie on the page with a 1px divider outline (or the theme's `--ha-card-border-color`) and no shadow. Depth below the card plane is a recessed gray well (copy fields, validity track). Selection and status are tonal tints. Shadows appear only for things that float above the page or respond to a press.

### Shadow Vocabulary
- **Button lift** (`box-shadow: 0 1px 3px rgba(0, 0, 0, .24)`): filled buttons on hover only.
- **Toast** (`box-shadow: 0 4px 12px rgba(0, 0, 0, .3)`): the copy confirmation snackbar.
- **Dialog** (`box-shadow: 0 12px 32px rgba(0, 0, 0, .28)`): the modal confirm dialog, over a 40% black scrim.

### Named Rules
**The Outlined Not Lifted Rule.** A card is a 1px outline on a flat plane. If something needs more presence, it gets a tint or a heading, not a shadow.

## Shapes

Corners follow HA's radius family. Cards, choice cards, and the QR backing use the theme's card radius (`--ha-card-border-radius`, 12px by default), and expansion-panel summaries and table wraps clip to it at the card's edges. Inputs, filter chips, alerts, copy fields, and the toast use 8px. Buttons are full pills (20px on a 44px minimum height; the file-picker button 18px on 36px), the search field is a pill, status chips are pills with a leading 8px dot, and icon buttons, tile icons, step counters, and the brand mark are circles. The confirm dialog uses 28px. The validity bar is a 6px track with 3px ends. Borders are always 1px; selected choices double theirs with a 1px inset ring rather than a heavier stroke.

## Components

### Buttons
Quiet pills that follow ha-button.
- **Shape:** full pill (20px radius, 44px minimum height), label weight 14px with 0.02em tracking, optional 18px leading icon with an 8px gap.
- **Filled:** deep accent fill with white text, 0 20px padding. The default action of a form or card.
- **Hover / Focus:** fill darkens 12% and gains the button-lift shadow over 150ms. Focus is a 2px focus-color outline at a 2px offset (global), using accent ink in the active theme.
- **Text:** transparent with accent ink, 0 12px padding; hover is a 10% primary tint. Used for secondary actions in card action bars.
- **Danger:** danger fill (filled) or bad ink (text). Destructive submits go through the confirm dialog.
- **Disabled:** hover wash background, secondary ink, no shadow.
- **Icon button:** 44px circle, 20px icon in secondary ink, hover wash plus full-strength text color. Every copy, download, and remove action in a row uses it, with an aria-label and title.

### Chips
- **Filter chips:** 44px minimum height, 8px radius, 1px outline, label weight, optional 18px icon and a secondary-ink count. Selected (`aria-current`) is a 16% primary tint with no border.
- **Status chips:** 24px pills, 12px medium text, 14% status tint with a solid 8px status dot and ink-mixed label. Kinds: ok, warn, bad, info, neutral.

### Cards / Containers
- **Corner Style:** theme card radius (12px).
- **Background:** card white / card charcoal.
- **Shadow Strategy:** none (see Elevation).
- **Border:** 1px divider.
- **Internal Padding:** header 16px 16px 8px with a 20px title and an optional full-width description; content 0 16px 16px, or flush for rows and tables; an action bar with a top divider, 8px 12px padding, right-aligned buttons.
- **Subhead:** a medium secondary-ink label with a top divider (16px 16px 4px) that names a group of rows inside a card, as Downloads does on the Authority card.

### Inputs / Fields
- **Style:** card background, 1px outline, 8px radius, 44px minimum height, 10px 12px padding. Labels sit above at medium weight with 6px below; hints sit under at 12px in secondary ink. Text areas are monospace, 96px minimum, vertically resizable.
- **Hover / Focus:** border goes to text color on hover; on focus the border and a 1px ring use focus-color (no outline).
- **Search:** a pill with a 20px magnifier inset 12px, filtering the table as you type.
- **File picker:** the native control with its button restyled as a 36px outlined pill in accent ink.
- **Radios and checkboxes:** native, 18px, `accent-color` accent fill (selected marks remain legible).
- **Field help:** direct hint text is associated with the field controls through `aria-describedby` by the shared script.
- **Secrets:** password fields receive a Show/Hide text button with `aria-controls`, `aria-pressed`, and an accessible name that includes the field label.
- **Invalid and submitting states:** native validation opens enclosing expansion sections so invalid controls are reachable; server errors receive focus. Submitted POST forms expose `aria-busy`, disable submit buttons, and show “Working…”. Returning through the browser cache reloads the page to restore the controls.

### Navigation
- **Toolbar:** sticky, 56px, page-gray background with a bottom divider, 20px title, then tabs at full height.
- **Tabs:** Certificates, Enroll, IPSK, Authority, and Settings; icon (20px) plus label, secondary ink, 0 20px padding. Hover is the wash plus full-strength text color. Active is accent ink with a 2px primary underline inset 12px with rounded top corners.
- **Mobile:** tabs become a fixed bottom bar; each tab is an equal column with the icon above a 12px label, and the indicator moves to the top edge, inset 25%.
- **Settings navigation:** a five-row hub leads to Certificates, Enrollment & Wi-Fi, IPSK, Identity & access, and System. Each category has focused subpages. Desktop subpages use a 240px sticky sidebar with 44px navigation targets and breadcrumbs; at 900px and below, a native disclosure replaces the sidebar. The menu stays usable without JavaScript. Home Assistant-managed options show a redacted saved summary and an explicit configuration link.
- **Detail pages:** a back icon button replaces the tabs.
- **Skip link:** admin and public pages expose “Skip to content” on keyboard focus and link to the main content landmark.

### Data Table
After ha-data-table: 48px medium secondary-ink headers, 12px 16px cells, divider rules, tabular numerals. Whole rows are links (a stretched row link), with the hover wash and, on keyboard focus, a focus-color inset rule above and below. Secondary lines sit under the name at 13px. Columns marked hide-mobile drop at 640px and their values move into the name's subline.

### Settings Rows and Key-Value Rows
- **Settings row:** 64px minimum, 12px 16px, a 24px secondary-ink icon, title and subtitle, trailing icon-button actions; rows are separated by a divider.
- **Key-value row:** a 120–180px key column in secondary ink, the value, and an optional trailing copy button; 48px minimum. Stacks under 520px of card width.

### Expansion Panels
After ha-expansion-panel. A 56px summary row with a leading icon, a 16px title and secondary subtitle, an optional status chip, and a trailing chevron that rotates 180° on open (200ms ease-out). Panels are separated by dividers and clip to the card's corners. The body is 4px 16px 16px, or flush when it holds rows. A card header may head a card of panels; URL hashes open named reference sections. Task forms use related 56px disclosure summaries, divider-separated sections, and 20px body insets (16px on mobile), with the same hover wash and rotating chevron.

### Choice Cards
Large radio choices for a decision the user must read. Each is a 12px-radius outlined card with a radio, a 24px accent-ink icon, a 16px medium title, and a secondary description. The checked choice gets a primary border, a 1px inset primary ring, and a 6% primary tint. A key-value detail block inside a choice appears only while that choice is checked, so the consequences of the selected option are visible and the other option's are not.

### Alerts
After ha-alert: 8px radius, 10px 12px padding, a 12% status tint, a 24px ink-mixed status icon, an optional medium title. Kinds: info, warning, error (with `role="alert"`), success.

### Health Tiles
One outlined card holding four tiles in a row, separated by vertical dividers: a 40px circular icon in a 16% status tint, a 16px medium value, a secondary label. A tile may be a link that filters the list.

### Validity Bar
A 6px recessed track with a status-colored fill for the elapsed share of the certificate's lifetime and a 2px text-colored "now" mark, with start and end dates beneath in tabular secondary ink.

### Copy Field and Toast
A value that must be copied whole (a link, a one-time password) sits in a recessed 8px well in monospace with a trailing copy icon button. Every copy action confirms with the snackbar-charcoal toast, which rises 24px from the bottom center on a 400ms exponential ease-out and leaves after 2.4s; on mobile it clears the bottom bar.

### Confirm Dialog
A 28px-radius card-colored dialog, 440px wide, 22px title, right-aligned actions, over a 40% scrim. It fades and scales in from 94% over 280ms on the ease-out. Every irreversible form goes through it.

### Numbered Steps
For device owners: a list where each step has a 28px circular counter in a 16% primary tint with accent-ink medium numerals, 44px of left indent, 16px between steps.

## Do's and Don'ts

### Do:
- **Do** read every color from an HA custom property or a `color-mix()` of one, so the parent theme can override it.
- **Do** use accent ink for themed text and the deep accent fill behind white text; never the raw primary.
- **Do** show status as a 12–16% tint with an ink-mixed foreground and, on chips, an 8px dot.
- **Do** put a copy icon button next to every serial, fingerprint, URL, and password, and confirm it with the toast.
- **Do** inline MDI icons as SVG paths from the shared icon set at 24, 20, or 18px.
- **Do** keep reference values in collapsed expansion panels with hash-addressable ids, and keep the six tool routes available in shared navigation.
- **Do** use the accent-ink focus alias consistently for keyboard outlines, field rings, and linked-row indicators.
- **Do** associate field hints with controls, expose secret visibility through accessible toggles, and show invalid and submitting states through the shared form behavior.
- **Do** route every irreversible action through the confirm dialog.
- **Do** turn off the dialog animation, toast transition, and chevron rotation under `prefers-reduced-motion`.

### Don't:
- **Don't** hard-code a color the HA theme cannot override, beyond the toast, the QR backing, the scrim, and white button text.
- **Don't** add shadows to cards, rows, or panels; use the 1px outline and tonal tints.
- **Don't** use weights other than 400 and 500, or set headings in medium weight.
- **Don't** use monospace for prose, labels, or add-on option names.
- **Don't** fill a status chip, alert, or tile solid with its status color.
- **Don't** load external fonts, icons, scripts, or images; the CSP allows inline CSS and nonce'd inline JS only.

## Resident Wi-Fi captive onboarding

The resident portal shares the public enrollment brand, card header, card content inset, alerts and field styling. It starts with the default-PSK captive redirect and a device-address check. Recovery precedes personal-data collection. Mobile resident inputs use 16px text and actions have a 44px minimum height. Successful registration on the current device displays the password and completion action before a collapsed QR; it does not navigate away automatically. The admin resident table adds the hardware MAC as data, with a dash when unavailable.

IPSK opens on a focused Wi-Fi key inventory. Five local page links keep Wi-Fi
keys, registered devices, invitations and join codes separate, with the fifth
link opening central IPSK settings.
Key creation and QR network settings have their own URLs and explicit return
links. Each inventory owns its search, sorting, pagination and empty recovery;
key status belongs only to the key inventory. Counts stay alongside their list,
and only Create a key leads the inventory's actions. Device access retains
Wi-Fi self-service policy and limits, linking to shared authentication and the
user directory, with captive setup guidance disclosed below.
The main section label is IPSK; resident remains the name for the person using
Wi-Fi. Dates follow the existing readable UTC format.

Public resident pages reuse the shared nonce-protected script for copy feedback,
submission progress and conditional fields. The captured current-device address
stays read-only. Another-device selection reveals and requires its hardware MAC;
hidden fields are disabled. The no-script form remains usable with server-side
validation. Validation recovery preserves non-secret details. One-time success
starts with a save-password warning and a copy action. Current-device completion
explains finishing setup then joining the named network; another-device success
prioritizes scanning/downloading. Add another device and Finish session remain
secondary actions.

## Full audit refinements (2026-10-02)

Interactive action buttons, icon buttons and status filters have a 44px minimum
height; icon buttons also have a 44px minimum width. Narrow forms use 16px
input text. Settings definition rows keep values and their copy/download
actions inside the same definition. Inline text links are underlined and
scrollable tables expose a named keyboard focus target. Rows with three or
more actions place those actions below the text on narrow screens.

Password controls receive stable IDs, field-specific names and Show/Hide
state. POST progress preserves the clicked submit button's name and value.
Enrollment and Wi-Fi QRs use four quiet modules and an explicit white backing.
The [full audit report](.impeccable/audits/2026-10-02-full-audit.md) records
verification and the remaining deployment checks.

## Pre-install setup and help (2026-10-02)

Setup and checks follows native HA outlined cards and settings rows. Ordered
installation steps precede explicit read-only readiness checks. States are
written out; configured settings never imply successful device onboarding.
Help uses a search form and native disclosures. Public residents see a compact
ordered progress list and collapsed recovery guidance. Field errors name and
associate the affected control without retaining invitation/password drafts.
Inventories have independent page controls; sorting stays disclosed. On phones,
secondary tools are behind Other tools so the current task leads the viewport.
No change to the pinned HA font, tokens, CA ownership or MariaDB requirement.

## IPSK critique fixes (2026-10-02)

IPSK inventories preserve desktop table semantics and become stacked rows below
640px. Name and status lead each row, followed by labelled metadata and visible,
wrapping actions. Long names and attribution wrap without sideways scrolling.
Repeated action names include the key or invitation label for assistive technology.
Registered devices link to the exact key ID, with a return to the originating search.

Creation, QR settings and access settings retain non-secret drafts on failure.
Known validation errors name their field; passwords and new Duo secrets must be
re-entered. Key expiry offers No expiry, 1 day, 1 week, 30 days and custom hours.
The no-script form exposes hours directly. Resident attribution is a record label,
not an account selector. Invitations can carry a descriptive resident/purpose label;
older unlabelled records retain a stable invitation number.

Duo group fields appear when verification or the resident list needs them. SDK
fields appear only for verification. Hidden controls are disabled in the browser,
and omitted provider settings retain their saved values on the server. The form
works without JavaScript with all configuration fields available.

All public success modes repeat the one-time password warning. For the current
device, network/password copying and Finish setup precede the optional QR; for
another device, scanning/downloading leads. Private-address recovery shows its
platform instructions once and keeps other connection help in a disclosure.

Control outlines mix primary text at 54% opacity to exceed 3:1 against the
default light/dark card surfaces. Native checked controls use accent fill,
which contrasts with both surfaces and their check mark. Decorative card
dividers retain the quiet HA divider token.

## Central settings navigation (2026-10-03)

Configuration is grouped by purpose under Settings rather than distributed
across Tools and operational IPSK inventories. Existing editors retain their
validation, ingress URLs and CSRF handling. Saved add-on options have focused
category summaries and a Home Assistant configuration link; all top-level
options are accounted for, with an advanced complete reference under System.
Passwords and secrets never appear in the summaries. Native disclosure menus,
HA theme tokens and the five-tab mobile bar remain the visual contract.

Verification covered 22 routes at desktop, tablet, 390px and 320px widths, with
light and dark themes. All 88 confirmation views passed axe with zero incomplete
results or horizontal overflow. Keyboard and no-script navigation passed.
The dark error-chip ink was lightened after the first inspection found a 4.42:1
contrast ratio on the MDM “Not set” state. Evidence is under
`.impeccable/audits/settings-menu/`. No new independent critique score is claimed.

## Shared identity settings (2026-10-03)

Authentication and the user directory belong to Identity & access, independently
of the Wi-Fi feature. Each has a dedicated provider form with scoped saves,
masked retained secrets and focused validation recovery. The IPSK Device access
page holds application policy and device limits, with explicit links to the
shared configuration. Provider validation is extracted into identity_settings
and can run without an IPSK network or enabled portal. Existing saved option
keys and current Duo authentication semantics are retained for compatibility.
