# Core readiness

Notes on what it would take for `pax_ble` to land as a built-in integration in
[`home-assistant/core`](https://github.com/home-assistant/core). This is not a
commitment, timeline, or a request that Home Assistant adopt the project. HACS
and this repository stay the supported distribution path until a core PR merges
(if that ever happens).

## Goal

Ship Pax / Vent-Axia Bluetooth fan support as a first-party Home Assistant
integration so users can install it from Settings > Devices without HACS, and
without the custom-integration "not tested by Home Assistant" loader warning.

There is no "please adopt us" process. Core only accepts integrations that
arrive as a pull request meeting current quality rules. See
[Contributing an integration to Core](https://developers.home-assistant.io/docs/core/integration/contributing_to_core/).

## Precedents (similar integrations already in Core)

Several Bluetooth device integrations already live in Core. Closest analogues:

| Integration | Why it's comparable |
|-------------|---------------------|
| [`switchbot`](https://www.home-assistant.io/integrations/switchbot/) | Connectable BLE, active GATT sessions, fans and other actuators; protocol library on PyPI (`PySwitchbot`) |
| [`govee_ble`](https://www.home-assistant.io/integrations/govee_ble/), [`xiaomi_ble`](https://www.home-assistant.io/integrations/xiaomi_ble/), [`sensirion_ble`](https://www.home-assistant.io/integrations/sensirion_ble/), [`inkbird`](https://www.home-assistant.io/integrations/inkbird/) | Vendor BLE sensors via Bluetooth integration + dedicated PyPI parsers |
| [`oralb`](https://www.home-assistant.io/integrations/oralb/), [`ld2410_ble`](https://www.home-assistant.io/integrations/ld2410_ble/) | Small single-purpose BLE device integrations |

Core prefers a thin HA integration plus a versioned library on PyPI (or a
clearly owned async library), Bluetooth discovery where possible, config flow,
and tests. Copying `custom_components/pax_ble` into Core will not pass review.

Pax / Vent-Axia fans are closer to SwitchBot (connect, authenticate, poll/write)
than to advertisement-only sensors. Expect more work than a BTHome-style parser.

## Expectations

- HACS remains the primary install path for now. Do not promise users a Core
  merge date.
- Someone must own the Core submission and the integration after merge (ideally
  `@eriknn` plus helpers). Drive-by dumps get stalled or closed.
- The custom component would need a rewrite to match current Core conventions
  (entity patterns, `runtime_data`, translations, diagnostics, Bluetooth APIs).
  Renaming files is not enough.
- Keep the first Core PR small: the minimum useful platform set, not every
  select/number/switch from HACS on day one. See
  [keep PRs small](https://developers.home-assistant.io/docs/core/integration/contributing_to_core/).
- Review can sit idle for months, with intermittent comments. BLE PRs slow down
  further when reviewers lack matching hardware.
- Pax and Vent-Axia share protocols under different BLE names; Core may want
  clear supported-device docs and brand assets in
  [home-assistant/brands](https://github.com/home-assistant/brands).
- Product limits stay documented: ambient humidity gaps on some hardware
  revisions, PIN pairing quirks, BLE proxy slot contention. Core docs should
  state those limits, not hide them.

## Practical TODO (high level)

Order is approximate; tracks can overlap.

### 1. Device library (in-tree vs PyPI)

- Extract GATT protocol / device models out of `custom_components/pax_ble/devices/`
  into a standalone, versioned Python package (preferred: publish on PyPI),
  similar to how SwitchBot uses `PySwitchbot`.
- Keep the HA integration thin: config flow, coordinators, entities, strings.
- Document PIN auth, connectable requirements, and which models map to which
  protocol (Calima / Levante / Svara / Svensa).
- Prefer async-friendly APIs that work with HA's Bluetooth / bleak stack.

### 2. Bronze-level quality (minimum for new Core integrations)

New Core integrations must meet at least Bronze on the
[Integration quality scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/).
Rules are listed under
[Bronze](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules#-bronze)
(config flow, connection test before configure/setup, unique IDs,
`has_entity_name`, appropriate polling, docs stubs, branding, dependency
transparency, config-flow tests, and related items).

Checklist for this project:

- [ ] UI config flow with discovery and/or manual add; refuse duplicate entries
- [ ] Test connection (including PIN) before creating the entry
- [ ] Fail setup cleanly when the device cannot be reached
- [ ] Entity unique IDs + `has_entity_name = True`
- [ ] Sensible default poll interval; document fast-poll / boost behaviour
- [ ] Brand icons/logos submitted to the brands repo
- [ ] Full config flow test coverage (Bronze requires this)
- [ ] Docs PR to `home-assistant.io` (high-level description, install, removal)

Skip Silver/Gold/Platinum for the first Core PR. Land Bronze plus a narrow
useful surface, then iterate.

### 3. Align with Core Bluetooth patterns

- [ ] Use current Bluetooth integration helpers (discovery matchers, connectable
      advertisements, proxy-friendly connection handling)
- [ ] Coordinator / unavailable semantics consistent with Core (stale vs
      unavailable; no silent "success" on failed polls)
- [ ] `ConfigEntry.runtime_data` instead of ad-hoc `hass.data` patterns where
      Core expects it
- [ ] Translations (`strings.json`), entity categories, device classes where they
      already apply in the custom component

### 4. Tests beyond the config flow

Bronze mandates solid config-flow tests; reviewers will still expect:

- [ ] Unit tests for the device library (decode/encode, validation ranges)
- [ ] Integration tests with mocked BLE (no live hardware in CI)
- [ ] Coverage of at least one happy-path sensor/update cycle per supported
      protocol family you claim in the first PR

### 5. Process / people

- [ ] Explicit buy-in from the current codeowner to support a Core submission
- [ ] CLA signed for all authors on the Core PR
- [ ] Short architecture note: why not ESPHome-only / MQTT bridge; why
      connectable BLE is required
- [ ] Migration plan for existing HACS users (same domain vs new domain; entity
      ID stability - decide early)

### 6. First Core PR scope (suggested)

1. Library on PyPI with Calima/Svara read path (sensors + boost switch), or
   whatever the smallest useful set is.
2. Core integration: config flow + those entities only.
3. Docs + brands assets.
4. Follow-ups: selects, numbers, Svensa, diagnostics, quality-scale climb.

## Out of scope

- Silencing the custom-integration loader warning without a Core merge (manifest
  tweaks cannot do that).
- Shipping every HACS-era entity and option in the first Core PR.
- Guaranteeing ambient RH on hardware that reports below-threshold raw values
  (`unknown` is correct; Core will not invent ambient RH).

## Status

| Item | Today |
|------|--------|
| Distribution | HACS / manual `custom_components` |
| Core PR | Not started |
| Device library on PyPI | Not extracted |
| Bronze checklist | Not tracked in-repo yet |
| Codeowner commitment for Core | TBD |

When real work starts, replace this table with links to the PyPI package, the
Core PR, and a `quality_scale.yaml` draft.
