# Localization and Accessibility Maintenance

## Scope
This document tracks current frontend localization and accessibility expectations for user-facing interface text.

## Supported application locales
The frontend currently supports these locales:

- en-GB
- cy-GB
- fr-FR
- de-DE
- es-ES
- zh-CN
- hi-IN
- ar
- bn-BD
- pt-BR
- ru-RU
- ur-PK

> Note: `en-US` has been removed from locale bundles, UI locale selection, and locale tests.

## Translation coverage policy
All user-facing UI strings (excluding dynamic proper names such as location names and operator names) must be represented in locale bundles.

Recent required key groups for parity across all locales:

- `notifications.sections.*`
- `notifications.loading*`
- `notifications.system.*`
- `notifications.live.*`
- `stopServices.*`
- `announce.stopServicesOpened`
- `announce.stopServicesClosed`

## Accessibility alignment notes
- Dynamic controls use localized ARIA labels via translation keys.
- Notification panel sections expose live regions for system announcements and live transport updates.
- Stop-services modal labels and table headers are localized.
- Colorblind mode notification styles preserve visible borders/focus affordances for state cues.

## Source of truth
For frontend text and behavior:

- `frontend/src/main.js`
- `frontend/src/index.html`
- `frontend/src/locales/*.json`
- `frontend/tests/accessibility.spec.js`

For project documentation navigation, use [docs/README.md](../README.md).
