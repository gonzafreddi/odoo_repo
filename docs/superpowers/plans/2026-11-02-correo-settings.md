# Correo Argentino Settings Implementation Plan

> **For agentic workers:** Execute inline in the approved session. Do not delegate.

**Goal:** Store Correo Argentino activation and account settings in Odoo and let Nest retrieve them through a restricted Odoo RPC method.

**Architecture:** Odoo `res.config.settings` owns the enable flag, username, password, customer ID, and origin postal code. A fixed Odoo model method guarded by a dedicated group returns only these settings to Nest. Nest caches configuration briefly in memory and continues to own technical API URL, timeout, package configuration, and quote persistence.

**Tech Stack:** Odoo 19 Python/XML, NestJS/TypeScript, existing XML-RPC `OdooService`.

**Spec:** `docs/superpowers/specs/2026-11-02-correo-settings-design.md`

## Global Constraints

- Credentials and customer identifiers must not be required in Nest environment variables.
- Credentials must never be returned to storefront clients or persisted in the quote database.
- The RPC getter must return only fixed Correo Argentino settings and require the dedicated integration group.
- Saving Settings with an empty password must preserve the stored password; clear it only through an explicit action.
- The integration remains disabled until an Odoo administrator enables it with complete credentials.
- Keep provider API URL, timeout, package box definitions, and shipping database connection in Nest deployment configuration.

---

## File map

Odoo files are under `custom-addons/sale_store_pickup/` in the `feat/correo-argentino` repo. Nest files are in `shop_back/ecommerce-api` on `dev`.

- Odoo `models/res_config_settings.py`: persistent settings and safe password save semantics.
- Odoo `models/res_config_settings.py`: fixed RPC getter with group check, alongside settings persistence.
- Odoo `models/__init__.py`: register models.
- Odoo `security/correo_security.xml`: dedicated integration group. The getter is a method on `res.config.settings` and performs its own group check; it exposes no CRUD model or arbitrary parameter access.
- Odoo `views/res_config_settings_views.xml`: Settings UI with password masked and configured-state indicator.
- Odoo `__manifest__.py`: load security before settings view.
- Nest `src/shipping/correo-argentino.client.ts`: fetch/cache settings via `OdooService`; no credentials from `ConfigService`.
- Nest `src/shipping/shipping.service.ts`: replace synchronous enabled checks with the client's async readiness check.
- Nest `src/config/env.validation.ts` and `.env.example`: remove moved settings, retain technical settings.

## Task 1: Add Odoo integration permissions and configuration settings

**Interfaces:** The Odoo user used by Nest will be assigned `sale_store_pickup.group_correo_integration`. The user can call only the fixed method `res.config.settings.get_correo_runtime_config()` and cannot choose parameter names.

- [x] Create a dedicated integration group with no broad implied administrator permissions.
- [x] Add `res.config.settings` fields for enable, username, customer ID, and origin postal code with `config_parameter` keys under `sale_store_pickup.correo_argentino.`.
- [x] Add password entry and explicit clear-password boolean without loading the saved password into the form. `set_values()` changes the stored password only for a non-empty entry or explicit clear action.
- [x] Prevent enabling when username, password, customer ID, or origin postal code is missing.
- [x] Add an Odoo `@api.model` getter on `res.config.settings` returning exactly `{enabled, username, password, customerId, originPostalCode}` after checking `has_group()`; access values using `sudo()` only after the check.
- [x] Add Settings view under the existing Sales settings form. Show whether a password is configured, never its value.
- [x] Register the settings model and load the security group before the Settings view in the manifest.
- [x] Parse changed XML, compile changed Python, and inspect field names and group references for consistency.

## Task 2: Read Odoo settings in Nest

**Consumes:** Odoo getter `res.config.settings.get_correo_runtime_config()`.

**Produces:** `CorreoArgentinoClient.assertReady()` and an internal runtime config with the exact getter fields.

- [x] Inject `OdooService` into `CorreoArgentinoClient`.
- [x] Add a 60-second in-memory configuration cache; never log, return from public endpoints, or persist its payload.
- [x] Implement `assertReady()` to retrieve configuration, reject disabled/incomplete settings with a sanitized service-unavailable response, and return the config for provider calls.
- [x] Pass runtime username/password to `/token`; use runtime customer ID and origin postal code for agencies/rates/import.
- [x] Keep provider token caching and 401 handling; clear cached token if the account fingerprint changes after configuration refresh.
- [x] Update `ShippingService` agency and quote flows to call `assertReady()` rather than the old synchronous `enabled` property.
- [x] Keep `CORREO_API_URL`, `CORREO_TIMEOUT_MS`, `CORREO_BOXES_JSON`, and `SHIPPING_DATABASE_URL` as Nest technical configuration.

## Task 3: Remove moved values from Nest environment configuration

- [x] Remove `CORREO_ENABLED`, `CORREO_USERNAME`, `CORREO_PASSWORD`, `CORREO_CUSTOMER_ID`, and `CORREO_ORIGIN_POSTAL_CODE` from `env.validation.ts`.
- [x] Remove conditional validation that required the moved settings when enabled; keep technical configuration validation and HTTPS enforcement.
- [x] Remove those five variables from `.env.example`, leaving Correo API URL, timeout, package boxes, and shipping database entries.
- [x] Search the Nest repository to confirm no runtime use of the removed environment names remains.

## Task 4: Verify and document operations

- [x] Run Nest production build and inspect its exit status.
- [x] Run Python compile and XML parsing for the Odoo addon changes.
- [x] Review diffs for accidental secret logging, response exposure, or generated artifacts.
- [x] Record deployment steps: upgrade Odoo addon, assign the Nest service user to the integration group, configure credentials in Odoo Settings, configure technical Nest variables, and keep integration disabled until QA credentials are confirmed.
- [ ] Do not run tests unless explicitly requested.

## Coverage review

- Settings ownership, masked secret, and explicit clear semantics: Task 1.
- Dedicated server-side RPC access and fixed return shape: Task 1.
- Nest memory-only cache, fail-closed behavior, and provider use: Task 2.
- Removal from Nest environment variables: Task 3.
- QA-disabled deployment and verification: Task 4.
