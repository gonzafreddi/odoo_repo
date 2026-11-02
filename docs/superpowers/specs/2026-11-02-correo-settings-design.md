# Correo Argentino credentials in Odoo Settings

## Status

Design approved in chat; awaiting review of this written spec before implementation.

## Goal

Let Suplex administrators configure and enable Correo Argentino from Odoo Settings. Nest must read the integration configuration server to server. Credentials must never be sent to the storefront or stored in Nest environment variables.

## Scope

Odoo Settings will own these values:

- Integration enabled.
- MiCorreo username and password.
- MiCorreo customer ID.
- Origin postal code.

The password uses a password input in Settings. Odoo persists these values as `ir.config_parameter` entries, following the standard `res.config.settings` `config_parameter` behavior. The operator must treat the Odoo database and its backups as secret-bearing systems.

Nest retains only technical configuration: API base URL, request timeout, package box definitions, and the shipping quote database connection. The current QA endpoint remains the default. No credentials or customer identifiers remain required in the Nest environment.

## Architecture and data flow

1. Add an Odoo Settings block for Correo Argentino in `sale_store_pickup`.
2. Expose a fixed, read-only Odoo model method for the Nest integration account to retrieve the four configured values. The method checks membership in a dedicated integration security group and returns only the known Correo keys; callers cannot request arbitrary config parameters.
3. Give the Odoo service account used by Nest that group during deployment. Keep the method inaccessible to public and ordinary portal users.
4. Nest's `CorreoArgentinoClient` gets credentials from the protected Odoo method, caches the result briefly in process memory, and uses it for token acquisition. It must not log credentials or provider authorization headers.
5. If disabled or incomplete, quote and agency endpoints fail closed with a clear service-unavailable response. Turning off the integration or changing credentials takes effect after the short cache expires; do not persist secrets in Nest's quote database.

## Settings behavior

- Saving an empty password must not accidentally erase an existing password. Settings UI must clearly represent an already configured secret without displaying its value.
- Enabling the integration requires username, password, customer ID, and origin postal code.
- Settings changes do not make a provider call during save; connectivity is exercised by the next agency or quote request.
- API URL remains a Nest deployment setting so operators do not accidentally point production at QA through the storefront-facing settings screen.

## Failure handling

- Missing or incomplete settings: return a sanitized configuration error; do not attempt provider authentication.
- Odoo configuration lookup failure: do not fall back to stale credentials beyond the short cache lifetime.
- Correo authentication/API failure: return a sanitized message and log only status and a correlation-safe summary.
- Configuration retrieval is server-to-server through the existing Odoo RPC channel; no new public Nest route is added.

## Deployment and compatibility

- Upgrade `sale_store_pickup` on the production-derived Odoo branch to create the settings fields and integration group.
- Add the Nest Odoo service account to the integration group.
- Remove `CORREO_ENABLED`, `CORREO_USERNAME`, `CORREO_PASSWORD`, `CORREO_CUSTOMER_ID`, and `CORREO_ORIGIN_POSTAL_CODE` from Nest validation and `.env.example` after the Odoo getter is deployed.
- Keep QA disabled until credentials are entered in Odoo and provider QA confirms token, agency, and rate calls.

## Verification

- Odoo module Python and XML parse successfully; Settings shows a masked password and round-trips other values.
- A user without the integration group cannot call the fixed getter; the Nest Odoo service account can.
- Nest build succeeds with the old credential environment variables absent.
- With incomplete or disabled Odoo settings, agencies and quotes stay unavailable; with valid QA settings, the existing quote flow can obtain agencies and rates.

## Out of scope

This change does not implement provider shipment import, label generation, tracking synchronization, or credential rotation workflows. Those depend on provider QA confirmation and the missing shipment/label contract identified in CA-01.
